import pprint

from bluesky.callbacks.zmq import RemoteDispatcher as ZmqRemoteDispatcher
from bluesky.callbacks.zmq import Publisher as ZmqPublisher

from event_model import RunRouter


zmq_listening_prefix = b"from-RE"

zmq_dispatcher = ZmqRemoteDispatcher(
    address=("127.0.0.1", 5678), prefix=zmq_listening_prefix
)

zmq_analysis_publisher = ZmqPublisher(
    address=("127.0.0.1", 4567), prefix=b"from-analysis"
)


def zmq_publish_from_analysis_factory(start_name, start_doc):
    print(
        f"zmq_publish_from_analysis_factory called with {start_name}:\n{pprint.pformat(start_doc)}\n"
    )

    def zmq_publish_from_analysis(name, doc):
        print(f"analysis consumer publishing {name}:\n{pprint.pformat(doc)}\n")
        zmq_analysis_publisher(name, doc)

    return [zmq_publish_from_analysis], []


zmq_dispatcher.subscribe(RunRouter(factories=[zmq_publish_from_analysis_factory]))

print(f"ANALYSIS CONSUMER IS LISTENING ON {zmq_listening_prefix}")
zmq_dispatcher.start()
