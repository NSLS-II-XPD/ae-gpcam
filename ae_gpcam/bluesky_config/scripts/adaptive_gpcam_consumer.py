import json
from queue import Queue

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
        if name == "start":
            if doc["batch_count"] > max_count:
                queue.put(None)
                return

        if name == "event_page":
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
                res = gp_optimizer_obj.ask(position=None, n=1)
                next_point = res["x"]
                func_eval = res["f(x)"]
                next_point = next_point.squeeze()
                func_eval = func_eval.squeeze()
                print("next requested point ", next_point)
                print("======================================")

            except NoRecommendation:
                queue.put(None)
            else:
                queue.put({k: v for k, v in zip(independent_keys, next_point)})

    rr = RunRouter([lambda name, doc: ([callback], [])])
    return rr, queue


# this process listens for 0MQ messages with prefix "rr" (roi-reduced)
zmq_listening_prefix = b"rr"

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

gp_optimizer = gp_optimizer.GPOptimizer(
    input_space_dimension=3,
    output_space_dimension=1,
    output_number=1,
    index_set_bounds=[],
    hyperparameter_bounds=[],
)

gpcam_recommender_run_router, _ = recommender_factory(
    gp_optimizer_obj=gp_optimizer,
    independent_keys=None,
    dependent_keys=None,
    variance_keys=None,
    max_count=1,
    queue=redis_queue,
)

zmq_dispatcher.subscribe(gpcam_recommender_run_router)


print(f"ADAPTIVE GPCAM CONSUMER LISTENING ON {zmq_listening_prefix}")
zmq_dispatcher.start()