import json
import pprint

import redis

from bluesky.callbacks.zmq import RemoteDispatcher as ZmqRemoteDispatcher
from bluesky_adaptive import recommendations
from bluesky_adaptive import per_start

from event_model import RunRouter

from bluesky_kafka import RemoteDispatcher


# kafka_dispatcher = RemoteDispatcher(
#     topics=["adaptive"],
#     bootstrap_servers="127.0.0.1:9092",
#     group_id="gpcam-recommender",
#     # "latest" should always work but
#     # has been failing on Linux, passing on OSX
#     consumer_config={"auto.offset.reset": "latest"},
#     polling_duration=1.0,
# )

zmq_listening_prefix = b"from-analysis"

zmq_dispatcher = ZmqRemoteDispatcher(
    address=("127.0.0.1", 5678), prefix=zmq_listening_prefix
)


class RedisQueue:
    "fake just enough of the queue.Queue API on top of redis"

    def __init__(self, client):
        self.client = client

    def put(self, value):
        print(f"pushing to redis queue: {value}")
        self.client.lpush("adaptive", json.dumps(value))


redis_queue = RedisQueue(redis.StrictRedis(host="localhost", port=6379, db=0))

step_recommender = recommendations.StepRecommender(1.5)
max_count = 15

recommender_factory, _ = per_start.recommender_factory(
    adaptive_obj=step_recommender,
    independent_keys=["motor"],
    dependent_keys=["det"],
    max_count=max_count,
    queue=redis_queue,
)
zmq_dispatcher.subscribe(recommender_factory)


def echo_factory(start_name, start_doc):
    print(f"echo_factory called with {start_name}\n{pprint.pformat(start_doc)}\n")

    def echo(name, doc):
        print(f"adaptive consumer received {name}:\n{pprint.pformat(doc)}\n")

    return [echo], []


echo_run_router = RunRouter(factories=[echo_factory])
zmq_dispatcher.subscribe(echo_run_router)

print(f"ADAPTIVE CONSUMER LISTENING ON {zmq_listening_prefix}")
zmq_dispatcher.start()
