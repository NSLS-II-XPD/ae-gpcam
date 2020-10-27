from functools import partial
import json
import pprint

import msgpack
import msgpack_numpy as mpn

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
#     deserializer=partial(msgpack.loads, object_hook=mpn.decode),
# )

zmq_dispatcher = ZmqRemoteDispatcher(
    address=("127.0.0.1", 5678),
    prefix=b'from-analysis'
)


class RedisQueue:
    "fake just enough of the queue.Queue API on top of redis"

    def __init__(self, client):
        self.client = client

    def put(self, value):
        print(f"pushing {value}")
        self.client.lpush("adaptive", json.dumps(value))


redis_queue = RedisQueue(redis.StrictRedis(host="localhost", port=6379, db=0))

step_recommender = recommendations.StepRecommender(1.5)
max_count = 15

recommender_factory, _ = per_start.recommender_factory(
    adaptive_obj=step_recommender,
    independent_keys=["motor"],
    dependent_keys=["det"],
    max_count=max_count,
    queue=redis_queue
)


def echo_factory(start_name, start_doc):
    def echo(name, doc):
        print(f"adaptive consumer received {name}:\n{pprint.pformat(doc)}\n")

    return [echo], []


echo_run_router = RunRouter(factories=[echo_factory])

# if the echo run router is subscribed first
# will it print the start doc before the exception?
zmq_dispatcher.subscribe(echo_run_router)
# what if the recommender factory just never gets the documents
#zmq_dispatcher.subscribe(recommender_factory)

print("ADAPTIVE CONSUMER IS READY TO START")
zmq_dispatcher.start()
