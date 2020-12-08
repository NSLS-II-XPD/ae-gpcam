import sys

from bluesky.callbacks.zmq import RemoteDispatcher

# listen for 0MQ messages from xf28id2-ca1:5578
zmq_server = "xf28id2-ca1:5578"
zmq_prefix = sys.argv[1].encode()

def echo(name, doc):
    print(f"got a {name} document with 0MQ prefix {zmq_prefix}")
    if "run_start" in doc:
        print(f"  run_start uid {doc['run_start']}")

d = RemoteDispatcher("xf28id2-ca1:5578", prefix=zmq_prefix)
d.subscribe(echo)
print("ZMQ ECHO CONSUMER IS RUNNING")
d.start()
