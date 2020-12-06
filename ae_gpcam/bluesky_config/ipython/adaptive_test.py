from bluesky_adaptive.per_start import (
    recommender_factory,
)
from bluesky_adaptive.recommendations import SequenceRecommender
from bluesky import RunEngine
from bluesky.callbacks.core import LiveTable
import bluesky.plans as bp
from ophyd.sim import SynAxis


class BatchLiveTable(LiveTable):
    def start(self, doc):
        if self._start is not None:
            if doc.get("batch_id", "") == self._start.get("batch_id"):
                return
        super().start(doc)

    def stop(self, doc):
        ...

    def descriptor(self, doc):

        if doc["name"] != self._stream:
            return

        if len(self._descriptors):
            self._descriptors.add(doc["uid"])
        else:
            super().descriptor(doc)


lt = BatchLiveTable(["ctrl_Ti", "ctrl_temp", "ctrl_anneal_time", "x", "y"])

y = SynAxis(name="y")
x = SynAxis(name="x")


RE = RunEngine()
RE.subscribe(lt)

recommender = SequenceRecommender([[30, 340, 450], [35, 340, 450], [35, 400, 450]])

cb, queue = recommender_factory(
    recommender, ["ctrl_Ti", "ctrl_temp", "ctrl_anneal_time"], ["x"]
)

pair = single_strip_set_transform_factory(single_data)
snap_function = snap_factory(single_data, time_tol=5, temp_tol=10, Ti_tol=5)

RE(
    adaptive_plan(
        [],
        (30, 460, 30 * 60),
        to_recommender=cb,
        from_recommender=queue,
        real_motors=(x, y),
        transform_pair=pair,
        snap_function=snap_function,
    )
)
