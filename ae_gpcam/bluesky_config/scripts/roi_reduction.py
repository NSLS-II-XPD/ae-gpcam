import numpy as np
import time

from event_model import RunRouter
from event_model import DocumentRouter
from event_model import compose_run
from bluesky.callbacks.zmq import RemoteDispatcher
from bluesky.callbacks.zmq import Publisher as zmqPublisher

# TODO change this to the location on XPD
zmq_publisher = zmqPublisher("127.0.0.1:4567", prefix=b"roi:")


class ROIPicker(DocumentRouter):
    def __init__(self, publisher):
        self._pub = publisher
        self.desc_bundle = None

    def start(self, doc):
        self._source_uid = doc["original_start_uid"]
        self.start_bundle = compose_run(
            metadata=dict(raw_uid=self._source_uid, integrated_uid=doc["uid"])
        )
        self._pub("start", self.start_bundle.start_doc)

    def event_page(self, doc):
        if self.desc_bundle is None:
            self.desc_bundle = self.start_bundle.compose_descriptor(
                name="primary",
                data_keys={
                    "I_00": {
                        "dtype": "number",
                        "source": "computed",
                        "units": "arb",
                        "shape": [],
                    },
                    "Q_00": {
                        "dtype": "number",
                        "source": "computed",
                        "units": "arb",
                        "shape": [],
                    },
                    "ctrl_Ti": {
                        "dtype": "number",
                        "source": "computed",
                        "units": "arb",
                        "shape": [],
                    },
                    "ctrl_annealing_time": {
                        "dtype": "number",
                        "source": "computed",
                        "units": "arb",
                        "shape": [],
                    },
                    "ctrl_temp": {
                        "dtype": "number",
                        "source": "computed",
                        "units": "arb",
                        "shape": [],
                    },
                },
            )
            self._pub("descriptor", self.desc_bundle.descriptor_doc)
        peak_locations = (2.63, 2.7)
        out = []
        # TODO look this up!
        # It appears that xpdan does not propogate additional keys, so we will
        # need to reach back into databroker to pull out the raw data!
        orig_uid = self._source_uid
        ti = 0.5
        at = 5
        temp = 450
        for Q, I in zip(doc["data"]["q"], doc["data"]["mean"]):
            # TODO add background subtraction
            # TODO account for dQ in averaging
            start, stop = np.searchsorted(Q, peak_locations)
            peak = np.sum(np.array(I[start : stop + 1]))
            data = {
                "I_00": peak,
                "Q_00": np.mean(peak_locations),
                "ctrl_Ti": ti,
                "ctrl_annealing_time": at,
                "ctrl_temp": temp,
            }
            _ts = time.time()
            ts = {k: _ts for k in data}
            self._pub("event", self.desc_bundle.compose_event(data=data, timestamps=ts))

        print(out)

    def stop(self, doc):
        stop_doc = self.start_bundle.compose_stop()
        self._pub("stop", stop_doc)


def PeakAreaCal(data, roi):
    """
    Parameters
    ----------
    data : float array
        data[0] : angle or q
        data[1] : intensity
    roi : flow array, region of interest for the angle or q value
        roi [0] : lower bound of the angle or q value
        roi [1] : upper bound of the angle or q value

    Returns
    -------
    area_sum : float
       sum of the area under the peak
    """

    # #readout row numbers with q value
    begin = data.iloc[(data[0] - roi[0]).abs().argsort()[:1]].index.tolist()[0]
    end = data.iloc[(data[0] - roi[1]).abs().argsort()[:1]].index.tolist()[0]

    # average the intensity of beginning and ending of peak
    average_begin = (data[1][begin] + data[1][begin - 1] + data[1][begin - 2]) / 3
    average_end = (data[1][end] + data[1][end + 1] + data[1][end + 2]) / 3

    # calculate the intensity of background
    background_sum = (average_begin + average_end) * (roi[1] - roi[0]) / 2

    # calculate the intensity of peak
    dQ = ((data[0][end] - data[0][end - 1]) + (data[0][begin] - data[0][begin - 1])) / 2
    intensity_sum = sum(data[1][begin : end + 1]) * dQ

    # Calculate the peak area by minus background intensity from total intensity
    area_sum = intensity_sum - background_sum

    return area_sum


def filter(name, doc):

    if doc.get("analysis_stage", "") == "integration":
        return [ROIPicker(zmq_publisher)], []
    return [], []


# TODO change this to the location on XPD
d = RemoteDispatcher("localhost:5678", prefix=b"an")
rr = RunRouter([filter])
d.subscribe(rr)
d.start()
