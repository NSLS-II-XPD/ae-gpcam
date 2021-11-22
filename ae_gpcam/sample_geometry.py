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


@dataclass(frozen=True)
class StripInfo:
    """Container for strip information."""

    temperature: int
    annealing_time: int
    # exclude the ti_fraction from the hash
    ti_fractions: list = field(hash=False)
    reference_x: float
    reference_y: float
    start_distance: float
    angle: float
    # treat this as a categorical
    thickness: int

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


def single_strip_transform_factory(
    temperature,
    annealing_time,
    ti_fractions,
    reference_x,
    reference_y,
    start_distance,
    angle,
    thickness,
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

    reference_x, reference_y : float
       The position of the reference point on the left edge of the
       sample (looking upstream into the beam) and on the center line
       of the sample strip.

    angle : float
       The angle in radians of the tilt.  The rotation point is the
       reference point.

    start_distance : float

       Distance along the strip from the reference point to the center
       of the first cell in mm.


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
    _thickness = int(thickness)

    cell_positions = np.arange(len(ti_fractions)) * cell_size

    def to_bl_coords(Ti_frac, temperature, annealing_time, thickness):
        if (
            _temperature != temperature
            or annealing_time != _annealing_time
            or _thickness != thickness
        ):
            raise ValueError

        if Ti_frac > np.max(ti_fractions) or Ti_frac < np.min(ti_fractions):
            raise ValueError

        d = (
            np.interp(Ti_frac, ti_fractions, cell_positions)
            - start_distance
            + (cell_size / 2)
        )

        # minus because we index the cells backwards
        return reference_x - np.cos(angle) * d, reference_y - np.sin(angle) * d

    def to_data_coords(x, y):
        # negative because we index the cells backwards
        x_rel = -(x - reference_x)
        y_rel = y - reference_y

        r = np.hypot(x_rel, y_rel)

        d_angle = -np.arctan2(y_rel, x_rel)

        from_center_angle = d_angle - angle
        d = np.cos(from_center_angle) * (r + start_distance - (cell_size / 2))
        h = -np.sin(from_center_angle) * r

        if not (np.min(cell_positions) < d < np.max(cell_positions)):
            raise ValueError

        if not (-cell_size / 2) < h < (cell_size / 2):
            raise ValueError

        ti_frac = np.interp(d, cell_positions, ti_fractions)

        return ti_frac, _temperature, _annealing_time, _thickness

    return TransformPair(to_bl_coords, to_data_coords)


def strip_list_transform_factory(strips, *, cell_size=4.5):
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
        by_annealing[(strip.temperature, strip.annealing_time, strip.thickness)].append(
            (strip, pair)
        )
        by_strip[strip] = pair

    def forward(Ti_frac, temperature, annealing_time, thickness):
        candidates = by_annealing[(temperature, annealing_time, thickness)]

        # we need to find a strip that has the right Ti_frac available
        for strip, pair in candidates:
            if strip.ti_min <= Ti_frac <= strip.ti_max:
                return pair.forward(Ti_frac, temperature, annealing_time, thickness)
        else:
            # get here if we don't find a valid strip!
            raise ValueError

    def inverse(x, y):
        # the y value fully determines what strip we are in
        for strip, pair in by_strip.items():
            if (
                strip.reference_y - cell_size / 2
                < y
                < strip.reference_y + cell_size / 2
            ):
                return pair.inverse(x, y)

        else:
            raise ValueError

    return TransformPair(forward, inverse)


def snap_factory(strip_list, *, temp_tol=None, time_tol=None, Ti_tol=None):
    """
    Generate a snapping function with given strips and tolerances.

    Thickness is always snapped to {0, 1} and tolerated it if fails.

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

    def snap(Ti, temperature, annealing_time, thickness):
        l_strips = strips

        thickness = int(np.clip(np.round(thickness), 0, 1))

        l_strips = filter(lambda x: x.thickness == thickness, l_strips)

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

        try:
            best = min(l_strips, key=l2_norm)
        except ValueError:
            # try with the other thickness
            return snap(Ti, temperature, annealing_time, {0: 1, 1: 0}[thickness])
        # clip Ti fraction to be within the selected strip
        best_Ti = np.clip(Ti, best.ti_min + 1.0, best.ti_max - 1.0)

        return best_Ti, best.temperature, best.annealing_time, best.thickness

    snap.tols = {
        k: v
        for k, v in zip(["temp", "time", "Ti"], [temp_tol, time_tol, Ti_tol])
        if v is not None
    }

    return snap


def show_layout(strip_list, ax=None, *, cell_size=4.5):
    """
    Make a nice plot of the strip layout.

    Parameters
    ----------
    strip_list : List[StripInfo]
        The configuration of the strips

    ax : Optional[Axes]
        The axes to put the plot onto

    cell_size : float
        The size of the cells.
    """
    if ax is None:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()

    cmap = mcm.get_cmap("magma")
    norm = mcolors.Normalize(0, 100)
    # state_map = {0: "thick", 1: "thin"}
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
                (x - cell_size / 2, y - cell_size / 2,),
                cell_size,
                cell_size,
                color=color,
            )
            ax.add_patch(rect)
            cells[strip].append(
                ax.text(x, y, f"{ti_frac}", ha="center", va="center", color="w",)
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
