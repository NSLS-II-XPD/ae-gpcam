import argparse
from itertools import count
import pprint

from bluesky.callbacks.zmq import Publisher
from databroker import Broker
from event_model import unpack_event_page, unpack_datum_page


arg_parser = argparse.ArgumentParser()

arg_parser.add_argument("--db-name", type=str, default="xpd")
arg_parser.add_argument("--run-id", type=str, required=True)
# publish 0MQ messages at XPD from xf28id2-ca1:5577
# subscribe to 0MQ messages at XPD from xf28id2-ca1:5578
arg_parser.add_argument("--zmq-host", type=str, default="xf28id2-ca1")
arg_parser.add_argument("--zmq-publish-port", type=int, default=5577)
arg_parser.add_argument("--zmq-publish-prefix", type=str, default="raw")

args = arg_parser.parse_args()
pprint.pprint(vars(args))

db = Broker.named("xpd")

zmq_publisher = Publisher(
    f"{args.zmq_host}:{args.zmq_publish_port}", prefix=args.zmq_publish_prefix.encode()
)

extra = count()
for name, doc in db[args.run_id].documents():
    print(f"trying to emit {name}")
    doc = dict(doc)
    if name == "descriptor":
        doc["data_keys"]["extra"] = {
            "dtype": "number",
            "source": "computed",
            "units": "arb",
            "shape": [],
        }
        zmq_publisher("descriptor", doc)
    if name == "event_page":
        for ev in unpack_event_page(doc):
            for j in range(5):
                new_seq = next(extra)
                ev["seq_num"] = new_seq
                ev["uid"] = str(uuid.uuid4())
                ev["data"]["extra"] = 5
                ev["timestamps"]["extra"] = 0
                zmq_publisher("event", ev)
    elif name == "datum_page":
        for datum in unpack_datum_page(doc):
            zmq_publisher("datum", datum)
    else:
        zmq_publisher(name, doc)
