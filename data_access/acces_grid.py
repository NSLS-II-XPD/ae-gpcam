import json
from dataclasses import dataclass, asdict, astuple, field
from collections import namedtuple, defaultdict

import numpy as np
import pandas as pd

import databroker


# ######
#
# helper code that should be in a library

TransformPair = namedtuple("TransformPair", ["forward", "inverse"])


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


def pre_process(data):
    I = data["mean"]
    Q = data["q"]
    x, y = (data["sample_x"], data["ss_stg2_y"])

    science_pos = []
    for _x, _y in zip(x, y):
        try:
            rp = pair.inverse(_x, _y)
        except ValueError:
            # the grid scan was not constrained to valid location
            rp = (np.nan,) * 4
        science_pos.append(rp)

    science_pos = pd.DataFrame(
        science_pos,
        columns=("ctrl_Ti", "ctrl_temp", "ctrl_annealing_time", "ctrl_thickness"),
    )

    roi = np.array([compute_peak_area(q, i, *peak_location) for q, i in zip(Q, I)])

    return science_pos, x, y, Q, I, roi


def mask(science_pos, x, y, Q, I, roi):
    i_mask = ~pd.isna(science_pos["ctrl_Ti"])

    return (
        science_pos[i_mask],
        x.values[i_mask],
        y.values[i_mask],
        Q.values[i_mask],
        I.values[i_mask],
        roi[i_mask],
    )


# ######################
#
# set up


strip_list = load_from_json("layout.json")
pair = single_strip_set_transform_factory(strip_list)
cat = databroker._drivers.msgpack.BlueskyMsgpackCatalog("*.msgpack")
h = cat["73ac6ea4-a528-4fb7-ae2f-eb44ed8d684d"]
peak_location = [2.925, 2.974]

# ######################
#
# data extraction / computation


data = h.primary.read()
science_pos, x, y, Q, I, roi = pre_process(data)
science_pos, x, y, Q, I, roi = mask(science_pos, x, y, Q, I, roi)
