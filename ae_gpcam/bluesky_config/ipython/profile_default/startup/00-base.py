import logging
import json
from queue import Empty

import IPython

import redis

from bluesky import RunEngine

from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.callbacks.zmq import Publisher as zmqPublisher
from bluesky_kafka import Publisher as kafkaPublisher

import databroker
import happi.loader


logger = logging.getLogger("databroker")
logger.setLevel("DEBUG")
handler = logging.StreamHandler()
handler.setLevel("DEBUG")
logger.addHandler(handler)

ip = IPython.get_ipython()

hclient = happi.Client(path="/usr/local/share/happi/test_db.json")
db = databroker.catalog["MAD"]

RE = RunEngine()
bec = BestEffortCallback()

zmq_publisher = zmqPublisher(address="127.0.0.1:4567", prefix=b"from-RE")

# kafka_publisher = kafkaPublisher(
#     topic="mad.bluesky.documents",
#     bootstrap_servers="127.0.0.1:29092",
#     key="bluesky-pods",
#     # work with a single broker
#     producer_config={
#         "acks": 1,
#         "enable.idempotence": False,
#         "request.timeout.ms": 5000,
#     },
# )


RE.subscribe(zmq_publisher)
RE.subscribe(bec)


class RedisQueue:
    def __init__(self, client):
        self.client = client

    def put(self, value):
        self.client.lpush("adaptive", json.dumps(value))

    def get(self, timeout=0, block=True):
        if block:
            ret = self.client.blpop("adaptive", timeout=timeout)
            if ret is None:
                raise TimeoutError
            return json.loads(ret[1])
        else:
            ret = self.client.lpop("adaptive")
            if ret is not None:
                return json.loads(ret)
            else:
                raise Empty


from_recommender = RedisQueue(redis.StrictRedis(host="localhost", port=6379, db=0))
# you may have to run this twice to "prime the topics" the first time you run it
# RE(adaptive_plan([det], {motor: 0}, to_recommender=None, from_recommender=from_recommender))


devs = {v.name: v for v in [happi.loader.from_container(_) for _ in hclient.all_items]}

ip.user_ns.update(devs)

# do from another
# http POST 0.0.0.0:8081/add_to_queue plan:='{"plan":"scan", "args":[["det"], "motor", -1, 1, 10]}'
# http POST 0.0.0.0:8081/add_to_queue plan:='{"plan":"count", "args":[["det"]]}'
