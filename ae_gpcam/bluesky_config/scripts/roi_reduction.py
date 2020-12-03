import numpy as np
import time

from event_model import RunRouter
from event_model import DocumentRouter
from event_model import compose_run
from bluesky.callbacks.zmq import RemoteDispatcher
from bluesky.callbacks.zmq import Publisher as zmqPublisher


class ROIPicker(DocumentRouter):
    def __init__(self, publisher, peak_location):
        self._pub = publisher
        self.desc_bundle = None
        self._peak_location = peak_location

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
        peak_location = self._peak_location
        out = []
        # TODO look this up!
        # It appears that xpdan does not propogate additional keys, so we will
        # need to reach back into databroker to pull out the raw data!
        orig_uid = self._source_uid
        ti = 0.5
        at = 5
        temp = 450
        for Q, I in zip(doc["data"]["q"], doc["data"]["mean"]):

            data = {
                "I_00": compute_peak_area(Q, I, *peak_location),
                # pick the center of the peak as the Q
                "Q_00": np.mean(peak_location),
                # mirror out the control values
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


def compute_peak_area(Q, I, q_start, q_stop):
    """
    Integrated area under a peak with estimated background removed.

    Estimates the background by averaging the 3 values on either side
    of the peak and subtracting that as a constant from I before
    integrating.

    Parameters
    ----------
    Q, I : array
        The q-values and binned intensity.  Assumed to be same length.

    q_start, q_stop : float
        The region of q to integrate.  Must be in same units as the Q.

    Returns
    -------
    peak_area : float

    """

    # figure out the index of the start and stop of the q
    # region of interest
    start, stop = np.searchsorted(Q, (q_start, q_stop))
    # add one to stop because we want the index after the end
    # value not the one before
    stop += 1
    # pull out the region of interest from I.
    data_section = I[start:stop]
    # pull out one more q value than I because we want the bin widths.
    q_section = Q[start : stop + 1]
    # compute width of each of the Q bins.
    dQ = np.diff(q_section)
    # estimate the background level by averaging the 3 and and 3 I(q) outside of
    # our ROI in either direction.
    background = (np.mean(I[start - 3 : start]) + np.mean(I[stop : stop + 3])) / 2
    # do the integration!
    return np.sum((data_section - background) * dQ)


def xpdan_result_picker_factory(zmq_publisher, peak_location):
    def xpdan_result_picker(name, doc):
        """"""
        if doc.get("analysis_stage", "") == "integration":
            return [ROIPicker(zmq_publisher, peak_location)], []
        return [], []

    return xpdan_result_picker


# TODO change this to the location on XPD
zmq_publisher = zmqPublisher("127.0.0.1:4567", prefix=b"from-analysis")
d = RemoteDispatcher("localhost:5678", prefix=b"an")
# peak_locations = (2.63, 2.7)
peak_location = (2.98, 3.23)
rr = RunRouter([xpdan_result_picker_factory(zmq_publisher, peak_location)])
d.subscribe(rr)
d.start()
