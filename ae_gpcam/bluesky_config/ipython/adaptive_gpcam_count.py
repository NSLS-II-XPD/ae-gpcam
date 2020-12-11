import pprint

import redis

import bluesky.plans as bp


class RedisQueue:
    "fake just enough of the queue.Queue API on top of redis"

    def __init__(self, client):
        self.client = client

    def put(self, value):
        print(f"pushing to redis queue: {value}")
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

redis_host = "xf28id2-srv1"
redis_port = 6379

redis_queue = RedisQueue(
    redis.StrictRedis(host=redis_host, port=redis_port, db=0)
)

def to_recommender(name, doc):
    print(f"to_recommender got\n{name}")
    #if name == "start":
    #    pprint.pprint(doc)

pair = single_strip_set_transform_factory(single_data)
#snap_function = snap_factory(single_data, time_tol=5, temp_tol=10, Ti_tol=None)
snap_function = snap_factory(single_data, time_tol=None, temp_tol=None, Ti_tol=None)

xrun(
    10,
    adaptive_plan(
        [pe2c],
        (18, 400, 7.5 * 60, 1),
        to_recommender=to_recommender,
        from_recommender=redis_queue,
        reccomender_timeout=60,
        real_motors=(sample_x, ss_stg2_y),
        transform_pair=pair,
        snap_function=snap_function,
        take_data=stepping_ct,
        exposure=20,
        max_runs=10000,
        rocking_range=0.5,
        num=3
    ),
    #print
    #lambda name, doc: pprint.pprint(doc) if name == 'start' else None
)
