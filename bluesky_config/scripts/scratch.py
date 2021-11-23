from typeing import Callable
import time
import uuid
import argparse
import random
import pprint
import collections

import numpy as np

from event_model import RunRouter, compose_run
from databroker._drivers.msgpack import BlueskyMsgpackCatalog
from suitcase.msgpack import Serializer

import pathlib


# This code will live in an agent that subscribes to the document stream from
# xpdan.  For testing, adapt this loop to look at files on disk / whatever you
# need to do.
def make_some_heuristics(
    num_samples: int, num_measurements: int, *, pub: Callable[str, dict], **md
) -> None:
    """Dummy function to simulate on-the-fly data quality checks


    Parameters
    ----------
    num_samples : int
        The number of samples to randomly draw from

    num_measurements : int
        How many "measurements" to add to the cache

    pub : Callable[str, dict]
        Function to push the name/doc pairs generated into ::

           def callback(name : str, doc : dict) -> None:
               ...

    **md : kwargs
        These will be stuffed into the start document.

    """
    for j in range(num_measurements):
        sample_num = random.randint(0, num_samples)

        # make the start document, stuff metadata here
        start_bundle = compose_run(
            metadata=dict(
                sample_num=sample_num,
                raw_uid=str(uuid.uuid4()),
                integrated_uid=str(uuid.uuid4()),
                **md,
            )
        )
        pub("start", start_bundle.start_doc)
        # make the descriptor, what keys you going to give me?
        # assume everything is just float64 scalars
        key_desc = {
            "dtype": "number",
            "dtype_str": "<f8",
            "source": "computed",
            "units": "arb",
            "shape": [],
        }
        desc_bundle = start_bundle.compose_descriptor(
            name="primary",
            data_keys={
                "snr": key_desc,
                "p2p": key_desc,
                "ratio": key_desc,
            },
        )
        pub("descriptor", desc_bundle.descriptor_doc)
        data = {k: v for k, v in zip(["snr", "p2p", "ratio"], np.random.rand(3))}
        _ts = time.time()
        ts = {k: _ts for k in data}
        pub("event", desc_bundle.compose_event(data=data, timestamps=ts))

        pub("stop", start_bundle.compose_stop())


# Argument handling
arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--document-cache", type=pathlib.Path)
args = arg_parser.parse_args()
pprint.pprint(vars(args))

# this code will live in the "decide what do to next agent"


# re-load any existing data and
cat = BlueskyMsgpackCatalog(str(args.document_cache / "*.msgpack"))
c = collections.Counter()
# iterate over all of the runs and do cummulative reduction (in this case just
# counting the number of measurements per sample.  In the real case this would
# be more sophisticated and feed the models with the current total sate of the
# world.
for h in cat.values():
    key = f'Sample {h.metadata["start"]["sample_num"]}'
    c[key] += 1
pprint.pprint(c)

# Set up the machinery to write generated documents to disk.  In the real case
# this should be subscribed next to the RunRouter that holds the agent.
rr = RunRouter([lambda name, doc: ([Serializer(args.document_cache, flush=True)], [])])

# turn the crank to generate some "synthetic" data.
make_some_heuristics(5, 15, pub=rr)
