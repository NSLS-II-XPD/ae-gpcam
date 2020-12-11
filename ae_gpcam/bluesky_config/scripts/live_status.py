from dataclasses import astuple

import numpy as np

import matplotlib.cm as mcm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from bluesky.callbacks.mpl_plotting import LiveScatter
import databroker
import matplotlib.pyplot as plt

from strip_structure import (
    single_strip_transform_factory,
    single_strip_set_transform_factory,
    load_from_json,
    compute_peak_area,
)

strip_list = load_from_json("/tmp/layout.json")


def plot_base(strip_list, ax=None, *, cell_size=4.5):
    """Make a nice plot of the strip layout."""
    if ax is None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()

    cmap = mcm.get_cmap("gray")
    norm = mcolors.Normalize(0, 100)
    cells = {}
    labels = {}
    for strip in strip_list:
        cells[strip] = []
        pair = single_strip_transform_factory(*astuple(strip))
        for j, ti_frac in enumerate(strip.ti_fractions):
            color = cmap(norm(ti_frac))
            x, y = pair.forward(
                ti_frac, strip.temperature, strip.annealing_time, strip.thickness
            )
            d = strip.start_distance - j * cell_size
            rect = mpatches.Rectangle(
                (
                    x - cell_size / 2,
                    y - cell_size / 2,
                ),
                cell_size,
                cell_size,
                color=color,
                zorder=-1,
            )
            ax.add_patch(rect)
            cells[strip].append(
                ax.text(
                    x,
                    y,
                    f"{ti_frac}",
                    ha="center",
                    va="center",
                    color="w",
                )
            )
            cells[strip].append(rect)
        d = cell_size * (len(strip.ti_fractions) - 0.5) - strip.start_distance
        labels[strip] = ax.annotate(
            f"{strip.temperature}°C\n{strip.annealing_time}s",
            xy=(
                strip.reference_x - d - cell_size / 2,
                strip.reference_y - np.sin(strip.angle) * d,
            ),
            xytext=(10, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            clip_on=False,
        )

    ax.relim()
    ax.autoscale()
    ax.figure.tight_layout()
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    # positive goes down on the beamline
    ax.invert_yaxis()
    ax.invert_xaxis()
    ax.set_aspect("equal")


class SummingScatter(LiveScatter):
    def __init__(self, *args, strip_list, **kwargs):
        self._strip_list = strip_list
        self.pair = single_strip_set_transform_factory(strip_list)
        self.latch = False
        LiveScatter.__init__(self, *args, **kwargs)

    def start(self, doc):
        if not self.latch:
            super().start(doc)
            self.latch = True
            # todo YOLO on thread safety!
            plot_base(strip_list, ax=self.ax)
        self._ae_info = doc["adaptive_step"]["snapped"]

    def event(self, doc):
        peak_location = [2.925, 2.974]
        ae_pos = self._ae_info
        x, y = self.pair.forward(
            *[
                ae_pos[k]
                for k in [
                    "ctrl_Ti",
                    "ctrl_temp",
                    "ctrl_annealing_time",
                    "ctrl_thickness",
                ]
            ]
        )
        doc["data"]["I_00"] = compute_peak_area(
            doc["data"]["q"], doc["data"]["mean"], *peak_location
        )
        doc["data"]["x"] = x
        doc["data"]["y"] = y
        super().event(doc)


cat = databroker._drivers.msgpack.BlueskyMsgpackCatalog(
    "/mnt/data/bnl/2020-12_ae/day2_reduced/*msgpack"
)
fig, ax = plt.subplots()
ss = SummingScatter("x", "y", "I_00", strip_list=strip_list, ax=ax)
for uid in cat:
    for name, doc in cat[uid].canonical(fill="no"):
        ss(name, doc)
ax.set_aspect("equal", adjustable="datalim")
ax.invert_xaxis()
ax.invert_yaxis()
