from typing import Callable
import argparse
import numpy as np
from queue import Queue
from collections import Counter
from event_model import RunRouter
from databroker._drivers.msgpack import BlueskyMsgpackCatalog
from suitcase.msgpack import Serializer
from bluesky_adaptive.utils import extract_event_page
from bluesky_adaptive.recommendations import NoRecommendation


class Agent:
    def __init__(
        self, n_samples: int, quality_function: Callable[[np.array], int] = None
    ):
        """
        Agent class that retains a counter of measurements at each sample,
        the index of the current sample, and a quality array with the current sample quality
        of each sample.

        Quality should be given as a natural number starting from 1 to the trained maximum.
        A regular default is to use {1: bad, 2: mediocre, 3:good}.
        It is expected that the sample quality can and should improve over time, and will be
        updated in the `tell` method as provided by the document stream.

        Parameters
        ----------
        n_samples: int
            Number of samples in measurement
        """
        self.counter = Counter()  # Counter of measurements
        self.current = None  # Current sample
        self.n_samples = n_samples
        self.cum_sum = dict()
        self.quality = np.zeros(self.n_samples)  # Current understood quality
        if quality_function is None:
            self.quality_function = self._default_quality
        else:
            self.quality_function = quality_function

    @staticmethod
    def _default_quality(arr) -> int:
        """Uses a proxy for Signal to Noise to break into 3 tiers."""
        SNR = np.max(arr) / np.mean(arr)
        if SNR < 2:
            return 1
        elif SNR < 3:
            return 2
        else:
            return 3

    def tell(self, y):
        """
        Tell's based on current sample only
        Parameters
        ----------
        y:

        Returns
        -------

        """
        self.counter[self.current] += 1
        if self.current in self.cum_sum:
            self.cum_sum[self.current] += y
        else:
            self.cum_sum[self.current] = y
        self.quality[self.current] = self.quality_function(self.cum_sum[self.current])

    def tell_many(self, xs, ys):
        """Useful for reload"""
        for x, y in zip(xs, ys):
            self.counter[x] += 1
            if self.current in self.cum_sum:
                self.cum_sum[x] += y
            else:
                self.cum_sum[x] = y
        for i in range(self.n_samples):
            self.quality[i] = self.quality_function(self.cum_sum[i])

    def ask(self, n):
        raise NotImplemented


class SequentialAgent(Agent):
    def __init__(self, n_samples):
        """
        Sequential agent that just keeps on going.

        Agent parent class retains a counter of measurements at each sample,
        the index of the current sample, and a quality array with the current sample quality
        of each sample.

        Quality should be given as a natural number starting from 1 to the trained maximum.
        A regular default is to use {1: bad, 2: mediocre, 3:good}.
        It is expected that the sample quality can and should improve over time, and will be
        updated in the `tell` method as provided by the document stream.

        Parameters
        ----------
        n_samples: int
            Number of samples in measurement
        """
        super().__init__(n_samples)

    def ask(self, n):
        return (self.current + 1) % self.n_samples


class MarkovAgent(Agent):
    def __init__(self, n_samples, max_quality, min_quality=1, seed=None):
        """
        Stochastic agent that moves preferentially to worse seeds.
        Queries a random transition and accepts with a probability of badness divided by range of quality.

        Agent parent class retains a counter of measurements at each sample,
        the index of the current sample, and a quality array with the current sample quality
        of each sample.

        Quality should be given as a natural number starting from 1 to the trained maximum.
        A regular default is to use {1: bad, 2: mediocre, 3:good}.
        It is expected that the sample quality can and should improve over time, and will be
        updated in the `tell` method as provided by the document stream.

        Parameters
        ----------
        n_samples: int
            Number of samples in measurement
        max_quality: int
            Maximum quality value
        min_quality: int
            Minimum quality value. Should be 1 unless you're doing something strange.
        """
        super().__init__(n_samples)
        self.max_quality = max_quality
        self.min_quality = min_quality
        self.rng = np.random.default_rng(seed)

    def ask(self, n):
        accept = False
        proposal = None
        while not accept:
            proposal = self.rng.integers(self.n_samples)
            if self.rng.random() < (self.max_quality - self.quality[proposal]) / (
                self.max_quality - self.min_quality
            ):
                accept = True

        return proposal


def reccomender_factory(
    adaptive_object,
    sample_index_key,
    sample_data_key,
    *,
    queue=None,
    cache_callback=None,
):
    if queue is None:
        queue = Queue()

    if cache_callback is None:
        prelim_callbacks = ()
    else:
        prelim_callbacks = [
            cache_callback,
        ]

    def callback(name, doc):
        """Assumes the start doc gives you the sample location,
        and the event_page gives quality info. The current index is updated at the start
        But the Agent quality matrix is only updated at tell."""
        # TODO: Validate the assumptions on formats
        print(f"callback received {name}")

        if name == "start":
            current_index = doc[sample_index_key]
            adaptive_object.current = current_index

        elif name == "event_page":
            data = extract_event_page(
                [
                    sample_data_key,
                ],
                payload=doc["data"],
            )
            adaptive_object.tell(data)

            try:
                next_point = adaptive_object.ask(1)
            except NoRecommendation:
                queue.put(None)
            else:
                queue.put({sample_index_key: next_point})
        else:
            print(f"Document {name} is not handled")

    rr = RunRouter([lambda name, doc: ([prelim_callbacks, callback], [])])
    return rr, queue


if __name__ == "__main__":
    from pathlib import Path
    import pprint

    arg_parser = argparse.ArgumentParser()
    # TODO: Add server arguments and setup
    arg_parser.add_argument("--document-cache", type=Path, default=None)
    arg_parser.add_argument("--agent", type=str, default="sequential")
    arg_parser.add_argument("-n", "--n-samples", type=int, default=30)
    args = arg_parser.parse_args()
    pprint.pprint(vars(args))

    ####################################################################
    # CHOOSE YOUR FIGHTER
    agent = {
        "sequntial": SequentialAgent(args.n_samples),
        "markov": MarkovAgent(args.n_samples, max_quality=3, seed=1234),
    }[args.agent]
    ####################################################################

    if args.document_cache is not None:
        cat = BlueskyMsgpackCatalog(str(args.document_cache / "*.msgpack"))
        for uid in cat:
            h = cat[uid]
            # TODO Update the agent in this space! Isn't this redundant with the factory callback?
            df = h.primary.read()
            start = h.metadata["start"]
            # or
            for name, doc in h.documents():
                ...

        cache_callback = Serializer(args.document_cache, flush=True)
    else:
        cache_callback = None

    ####################################################################
    # ENSURE THESE KEYS AND QUEUE ARE APPROPRIATE
    badseed_run_router, _ = reccomender_factory(
        adaptive_object=agent,
        sample_index_key="sample number",
        sample_quality_key="quality",
        queue=Queue(),
        cache_callback=cache_callback,
    )
    ####################################################################

    # TODO: Add server subscription
