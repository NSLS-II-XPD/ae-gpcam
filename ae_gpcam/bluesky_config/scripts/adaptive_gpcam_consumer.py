import argparse
import json
import pprint
from queue import Queue
import time

import numpy as np
import redis

from event_model import RunRouter

from bluesky_adaptive.recommendations import NoRecommendation
from bluesky_adaptive.utils import extract_event_page

from bluesky.callbacks.zmq import RemoteDispatcher as ZmqRemoteDispatcher

from gpcam import gp_optimizer


def recommender_factory(
    gp_optimizer_obj,
    independent_keys,
    dependent_keys,
    variance_keys,
    *,
    max_count=10,
    queue=None,
):
    """
    Generate the callback and queue for an Adaptive API backed recommender.

    This recommends a fixed step size independent of the measurement.

    For each Run (aka Start) that the callback sees it will place
    either a recommendation or `None` into the queue.  Recommendations
    will be of a dict mapping the independent_keys to the recommended
    values and should be interpreted by the plan as a request for more
    data.  A `None` placed in the queue should be interpreted by the
    plan as in instruction to terminate the run.

    The StartDocuments in the stream must contain the key
    ``'batch_count'``.


    Parameters
    ----------
    adaptive_object : adaptive.BaseLearner
        The recommendation engine

    independent_keys : List[str]
        The names of the independent keys in the events

    dependent_keys : List[str]
        The names of the dependent keys in the events

    variance_keys : List[str]
        The names of the variance keys in the events

    max_count : int, optional
        The maximum number of measurements to take before poisoning the queue.

    queue : Queue, optional
        The communication channel for the callback to feedback to the plan.
        If not given, a new queue will be created.

    Returns
    -------
    callback : Callable[str, dict]
        This function must be subscribed to RunEngine to receive the
        document stream.

    queue : Queue
        The communication channel between the callback and the plan.  This
        is always returned (even if the user passed it in).

    """

    if queue is None:
        queue = Queue()

    def callback(name, doc):
        # TODO handle multi-stream runs with more than 1 event!
        print(f"callback received {name}")
        if name == "start":
            if "batch_count" not in doc:
                print(f"  batch_count missing from {name} {doc['uid']}")

            elif doc["batch_count"] > max_count:
                queue.put(None)
                return

        elif name == "event_page":
            print(f"event_page: {pprint.pformat(doc)}")
            print(f"independent_keys: {pprint.pformat(independent_keys)}")
            print(f"dependent_keys: {pprint.pformat(dependent_keys)}")
            print(f"variance_keys: {pprint.pformat(variance_keys)}")
            independent, measurement, variances = extract_event_page(
                independent_keys, dependent_keys, variance_keys, payload=doc["data"]
            )
            # measurement = np.array([[np.sin(independent[0,0])]])
            variances[:, :] = 0.01
            value_positions = np.zeros((1, 1, 1))
            print("new measurement results:")
            print("x: ", independent)
            print("y: ", measurement)
            print("variance: ", variances)
            #################################
            #####HERE########################
            #################################
            ####independent, measurement, variances: 2d numpy arrays
            ####value pos: 3d numpy arrays
            lom = None
            print("telling data ...")
            if len(gp_optimizer_obj.points) in [5, 20, 100, 200, 400]:
                lom = "global"
            t0 = time.time()
            gp_optimizer_obj.tell(
                independent,
                measurement,
                variances=variances,
                init_hyperparameters=np.ones((3)),
                value_positions=value_positions,
                likelihood_optimization_method=lom,
                measurement_costs=None,
                measurement_costs_update=False,
                append=True,
            )
            t1 = time.time()
            print(f"tell() took {t1-t0:.2f}s")
            # print("current data set: ", gp_optimizer_obj.points)
            # print("---------------------------------------")
            # pull the next point out of the adaptive API
            try:
                #################################
                #####HERE########################
                #################################
                ##position
                ##number of asked measurements = 1
                ##bounds numpy 2d array
                ##objective_function_pop_size = 20
                ##max_iter = 20
                ##tol = 0.0001
                print("asking for point...")
                t0 = time.time()
                res = gp_optimizer_obj.ask(position=None, n=1)
                t1 = time.time()
                next_point = res["x"]
                func_eval = res["f(x)"]
                next_point = next_point.squeeze()
                func_eval = func_eval.squeeze()
                print(f"next point {next_point}")
                print(f"ask() took {t1-t0:.2f}s")
                print("======================================")

            except NoRecommendation:
                queue.put(None)
            else:
                queue.put({k: v for k, v in zip(independent_keys, next_point)})
        else:
            print(f"  document {name} is not handled")

    rr = RunRouter([lambda name, doc: ([callback], [])])
    return rr, queue


class RedisQueue:
    "fake just enough of the queue.Queue API on top of redis"

    def __init__(self, client):
        self.client = client

    def put(self, value):
        print(f"pushing to redis queue: {value}")
        self.client.lpush("adaptive", json.dumps(value))


arg_parser = argparse.ArgumentParser()

# talk to redis at XPD on xf28id2-srv1:6379
arg_parser.add_argument("--redis-host", type=str, default="xf28id2-srv1")
arg_parser.add_argument("--redis-port", type=int, default=6379)

# subscribe to 0MQ messages at XPD from xf28id2-ca1:5578
arg_parser.add_argument("--zmq-host", type=str, default="xf28id2-ca1")
arg_parser.add_argument("--zmq-subscribe-port", type=int, default=5578)
arg_parser.add_argument("--zmq-subscribe-prefix", type=str, default="rr")

args = arg_parser.parse_args()

pprint.pprint(vars(args))

# this process listens for 0MQ messages with prefix "rr" (roi-reduced)
zmq_dispatcher = ZmqRemoteDispatcher(
    address=(args.zmq_host, args.zmq_subscribe_port),
    prefix=args.zmq_subscribe_prefix.encode(),
)

redis_queue = RedisQueue(
    redis.StrictRedis(host=args.redis_host, port=args.redis_port, db=0)
)

gpopt = gp_optimizer.GPOptimizer(
    input_space_dimension=3,
    output_space_dimension=1,
    output_number=1,
    index_set_bounds=[[16, 81], [7.5, 60], [340, 460]],
    hyperparameter_bounds=[[0.001, 1e9], [0.001, 100], [0.001, 100], [0.001, 100]],
)

gpcam_recommender_run_router, _ = recommender_factory(
    gp_optimizer_obj=gpopt,
    independent_keys=["ctrl_Ti", "ctrl_annealing_time", "ctrl_temp"],
    dependent_keys=["I_00"],
    variance_keys=["I_00_variance"],
    max_count=1,
    queue=redis_queue,
)

zmq_dispatcher.subscribe(gpcam_recommender_run_router)


print(f"ADAPTIVE GPCAM CONSUMER LISTENING ON {args.zmq_subscribe_prefix.encode()}")
zmq_dispatcher.start()
