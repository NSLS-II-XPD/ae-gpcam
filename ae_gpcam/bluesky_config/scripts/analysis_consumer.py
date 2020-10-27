import pprint

from bluesky.callbacks.zmq import RemoteDispatcher as ZmqRemoteDispatcher
from bluesky.callbacks.zmq import Publisher as ZmqPublisher

from event_model import RunRouter


zmq_dispatcher = ZmqRemoteDispatcher(
    address=("127.0.0.1", 5678),
    prefix=b'adaptive'
)


def zmq_publish_from_analysis_factory(start_name, start_doc):
    zmq_analysis_publisher = ZmqPublisher(address=("127.0.0.1", 4567), prefix=b'from-analysis')

    def zmq_publish_from_analysis(name, doc):
        print(f"analysis consumer publishing {name}:\n{pprint.pformat(doc)}\n")
        zmq_analysis_publisher(name, doc)

    return [zmq_publish_from_analysis], []


rr = RunRouter(factories=[zmq_publish_from_analysis_factory])

zmq_dispatcher.subscribe(rr)
print("ANALYSIS CONSUMER IS READY TO START")
zmq_dispatcher.start()
