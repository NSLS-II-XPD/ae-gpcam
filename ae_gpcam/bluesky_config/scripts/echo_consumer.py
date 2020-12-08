import sys

from bluesky.callbacks.zmq import RemoteDispatcher


# listen for 0MQ messages from xf28id2-ca1:5578
zmq_server = "xf28id2-ca1:5578"
zmq_prefix = sys.argv[1].encode()

def echo(name, doc):
    print(f"got a {name} document with 0MQ prefix {zmq_prefix}")
    if name == "start":
        print(f"  start id {doc['uid']}")
    elif name == "descriptor":
        print(f"  start id {doc['run_start']}")
        print(f"  uid {doc['uid']}")
    elif name == "event":
        print(f"  descriptor id {doc['descriptor']}")
        print(f"  uid {doc['uid']}")

d = RemoteDispatcher("xf28id2-ca1:5578", prefix=zmq_prefix)
d.subscribe(echo)
print("ZMQ ECHO CONSUMER IS RUNNING")
d.start()
