"""Structures and helpers to defined sample layout."""

import json
from dataclasses import dataclass, asdict, astuple, field
from collections import namedtuple, defaultdict

import numpy as np
import matplotlib.cm as mcm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches


# These terms match the pseudo positioner code in ophyd and are standard
# in motion control.

# Forward: pseudo positions -> real positions
#     aka: data coordinates -> beamline coordinates
# Inverse: real positions       -> pseudo positions
#     aka: beamline coordinates -> data coordinates
TransformPair = namedtuple("TransformPair", ["forward", "inverse"])


def single_strip_transform_factory(
    temperature,
    annealing_time,
    ti_fractions,
    start_position,
    strip_center,
    *,
    cell_size=4.5,
):
    """
    Generate the forward and reverse transforms for a given strip.

    This assumes that the strips are mounted parallel to one of the
    real motor axes.  This only handles a single strip which has a
    fixed annealing time and temperature.

    Parameters
    ----------
    temperature : int
       The annealing temperature in degree C

    annealing_time : int
       The annealing time in seconds

    ti_fractions : Iterable
       The fraction of Ti in each cell (floats in range [0, 100])

       Assume that the values are for the center of the cells.

    start_position : float

       Coordinate in beamline coordinates in the direction along the
       strip in mm to the center of the first cell.

       Assumed to be 'x'

    strip_center : float
       Coordinate of the center of the strip in the direction
       transverse to the gradient in mm.

       Assumed to be 'y'

    cell_size : float, optional

       The size of each cell along the gradient where the Ti fraction
       is measured in mm.


    Returns
    -------
    transform_pair
       forward (data -> bl)
       inverse (bl -> data)

    """
    _temperature = int(temperature)
    _annealing_time = int(annealing_time)

    cell_positions = start_position + np.arange(len(ti_fractions)) * cell_size

    def to_bl_coords(Ti_frac, temperature, annealing_time):
        if _temperature != temperature or annealing_time != _annealing_time:
            raise ValueError

        if Ti_frac > np.max(ti_fractions) or Ti_frac < np.min(ti_fractions):
            raise ValueError

        x = np.interp(Ti_frac, ti_fractions, cell_positions)

        return x, strip_center

    def to_data_coords(x, y):
        if x < np.min(cell_positions) or x > np.max(cell_positions):
            raise ValueError

        if not ((strip_center - cell_size / 2) < y < (strip_center + cell_size / 2)):
            raise ValueError

        ti_frac = np.interp(x, cell_positions, ti_fractions)

        return ti_frac, _temperature, _annealing_time

    return TransformPair(to_bl_coords, to_data_coords)


@dataclass(frozen=True)
class StripInfo:
    """Container for strip information."""

    temperature: int
    annealing_time: int
    # exclude the ti_fraction from the hash
    ti_fractions: list[int] = field(hash=False)
    start_position: float
    strip_center: float

    # helpers to get the min/max of the ti fraction range.
    @property
    def ti_min(self):
        return min(self.ti_fractions)

    @property
    def ti_max(self):
        return max(self.ti_fractions)


def strip_list_to_json(strip_list, fname):
    """
    Write strip list information to a json file.

    Will over write if exists.

    Parameters
    ----------
    strip_list : List[StripInfo]

    fname : str or Path
        File to write
    """
    # TODO make this take a file-like as well
    with open(fname, "w") as fout:
        json.dump(strip_list, fout, default=asdict, indent="  ")


def load_from_json(fname):
    """
    Load strip info from a json file.

    Parameters
    ----------
    fname : str or Path
        File to write

    Returns
    -------
    list[StripInfo]

    """
    # TODO make this take a file-like as well
    with open(fname, "r") as fin:
        data = json.load(fin)

    return [StripInfo(**d) for d in data]


def single_strip_set_transform_factory(strips, *, cell_size=4.5):
    """
    Generate the forward and reverse transforms for set of strips.

    This assumes that the strips are mounted parallel to one of the
    real motor axes.

    This assumes that the temperature and annealing time have been
    pre-snapped.

    Parameters
    ----------
    strips : List[StripInfo]

    cell_size : float, optional

       The size of each cell along the gradient where the Ti fraction
       is measured in mm.

    Returns
    -------
    to_data_coords, to_bl_coords
    """
    by_annealing = defaultdict(list)
    by_strip = {}

    for strip in strips:
        pair = single_strip_transform_factory(*astuple(strip))
        by_annealing[(strip.temperature, strip.annealing_time)].append((strip, pair))
        by_strip[strip] = pair

    def forward(Ti_frac, temperature, annealing_time):
        candidates = by_annealing[(temperature, annealing_time)]

        # we need to find a strip that has the right Ti_frac available
        for strip, pair in candidates:
            if strip.ti_min <= Ti_frac <= strip.ti_max:
                return pair.forward(Ti_frac, temperature, annealing_time)
        else:
            # get here if we don't find a valid strip!
            raise ValueError

    def inverse(x, y):
        # the y value fully determines what strip we are in
        for strip, pair in by_strip.items():
            if (
                strip.strip_center - cell_size / 2
                < y
                < strip.strip_center + cell_size / 2
            ):
                return pair.inverse(x, y)
        else:
            raise ValueError

    return TransformPair(forward, inverse)


def snap_factory(strip_list, *, temp_tol=None, time_tol=None, Ti_tol=None):
    """
    Generate a snapping function with given strips and tolerances.

    Parameters
    ----------
    strips : List[StripInfo]

    temp_tol : int, optional
       If not None, only snap in with in tolerance range

    time_tol : int, optional
       If not None, only snap in with in tolerance range

    Ti_tol : int, optional
       If not None, only snap in with in tolerance range

    Returns
    -------
    snap_function

       has signature ::

          def snap(Ti, temperature, time):
              returns snapped_Ti, snapped_temperature, snapped_time
    """

    # make local copy to be safe!
    strips = tuple(strip_list)

    def snap(Ti, temperature, annealing_time):
        l_strips = strips

        # only consider strips close enough in temperature
        if temp_tol is not None:
            l_strips = filter(
                lambda x: abs(x.temperature - temperature) < temp_tol, l_strips
            )
        # only consider strips close enough in annealing time
        if time_tol is not None:
            l_strips = filter(
                lambda x: abs(x.annealing_time - annealing_time) < time_tol, l_strips
            )

        # only consider strips with Ti fractions that are with in tolerance
        if Ti_tol is not None:
            l_strips = filter(
                lambda x: x.ti_min - Ti_tol <= Ti <= x.ti_max + Ti_tol, l_strips
            )

        # Us an L2 norm to sort out what strips are "closest" it
        # (Temp, time) space
        def l2_norm(strip):

            return np.hypot(
                strip.temperature - temperature, strip.annealing_time - annealing_time
            )

        # TODO make error message better here if nothing within tolerance
        best = min(l_strips, key=l2_norm)
        # clip Ti fraction to be within the selected strip
        best_Ti = np.clip(Ti, best.ti_min, best.ti_max)

        return best_Ti, best.temperature, best.annealing_time

    snap.tols = {
        k: v
        for k, v in zip(["temp", "time", "Ti"], [temp_tol, time_tol, Ti_tol])
        if v is not None
    }

    return snap


_layout_template = [
    StripInfo(
        temperature=340,
        annealing_time=450,
        ti_fractions=[19, 22, 27, 30, 35, 40, 44, 49, 53],
        start_position=18.5,
        strip_center=0,
    ),
    StripInfo(
        temperature=340,
        annealing_time=1800,
        ti_fractions=[19, 20, 23, 28, 32, 37, 42, 46, 51, 56, 60],
        start_position=14.0,
        strip_center=0,
    ),
    StripInfo(
        temperature=340,
        annealing_time=3600,
        ti_fractions=[16, 18, 22, 25, 29, 34, 36, 43, 49, 53, 58, 62, 67],
        start_position=9.5,
        strip_center=0,
    ),
    StripInfo(
        temperature=400,
        annealing_time=450,
        ti_fractions=[17, 20, 23, 27, 31, 36, 41, 46, 51, 56, 61, 65, 69],
        start_position=9.5,
        strip_center=0,
    ),
    StripInfo(
        temperature=400,
        annealing_time=1800,
        ti_fractions=[20, 23, 27, 32, 37, 42, 47, 51, 57, 63, 67, 71, 75, 78, 81],
        start_position=5,
        strip_center=0,
    ),
    StripInfo(
        temperature=400,
        annealing_time=3600,
        ti_fractions=[19, 22, 25, 30, 35, 39, 45, 50, 55, 60, 65, 69, 73, 77, 79],
        start_position=5,
        strip_center=0,
    ),
    StripInfo(
        temperature=460,
        annealing_time=450,
        ti_fractions=[17, 20, 24, 28, 32, 37, 43, 48, 52, 58, 63, 67, 71, 75, 78],
        start_position=5,
        strip_center=0,
    ),
    StripInfo(
        temperature=460,
        annealing_time=15 * 60,
        ti_fractions=[17, 19, 22, 26, 31, 35, 40, 46, 51, 56, 61, 65, 69, 73, 76],
        start_position=5,
        strip_center=0,
    ),
    StripInfo(
        temperature=460,
        annealing_time=30 * 60,
        ti_fractions=[15, 18, 21, 25, 28, 33, 38, 43, 48, 53, 58, 63, 67, 71, 75],
        start_position=5,
        strip_center=0,
    ),
][::-1]

spacing = 0

thin_offset = 45.0
single_data = [
    StripInfo(
        **{**asdict(strip), "strip_center": (j * (4.5 + spacing) + thin_offset + 2.25)}
    )
    for j, strip in enumerate(_layout_template)
]

thick_offset = 0
single_data_thick = [
    StripInfo(
        **{**asdict(strip), "strip_center": j * (4.5 + spacing) + thick_offset + 2.25}
    )
    for j, strip in enumerate(_layout_template)
]


def show_layout(strip_list, ax=None, *, cell_size=4.5):
    if ax is None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()

    cmap = mcm.get_cmap("magma")
    norm = mcolors.Normalize(0, 100)

    cells = {}
    labels = {}
    for strip in strip_list:
        cells[strip] = []

        for j, ti_frac in enumerate(strip.ti_fractions):
            color = cmap(norm(ti_frac))
            rect = mpatches.Rectangle(
                (
                    strip.start_position + j * cell_size,
                    strip.strip_center - cell_size / 2,
                ),
                cell_size,
                cell_size,
                color=color,
            )
            ax.add_patch(rect)
            cells[strip].append(
                ax.text(
                    strip.start_position + (j + 0.5) * cell_size,
                    strip.strip_center,
                    f"{ti_frac}",
                    ha="center",
                    va="center",
                    color="w",
                )
            )
            cells[strip].append(rect)

        labels[strip] = ax.annotate(
            f"{strip.temperature}°C\n{strip.annealing_time}s",
            xy=(strip.start_position + (j + 1) * cell_size, strip.strip_center),
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
