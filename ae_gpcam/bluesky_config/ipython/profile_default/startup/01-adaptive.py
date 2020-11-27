"""Plan for running pgcam AE with a gradient TiCu sample."""

import uuid
import itertools
import json
from dataclasses import dataclass, asdict, astuple, field
from collections import namedtuple, defaultdict

import numpy as np
import matplotlib.cm as mcm
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from ophyd import Device, Signal, Component as Cpt

import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
from queue import Empty

# These terms match the pseudo positioner code in ophyd and are standard
# in motion control.

# Forward: pseudo positions -> real positions
#     aka: data coordinates -> beamline coordinates
# Inverse: real positions       -> pseudo positions
#     aka: beamline coordinates -> data coordinates
TransformPair = namedtuple("TransformPair", ["forward", "inverse"])


def single_strip_factory(
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


def single_strip_set_factory(strips, *, cell_size=4.5):
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
        pair = single_strip_factory(*astuple(strip))
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

    return snap


def adaptive_plan(
    dets,
    first_point,
    *,
    to_recommender,
    from_recommender,
    md=None,
    take_reading,
    transform_pair,
    real_motors,
    snap_function=None,
    reccomender_timeout=1,
):
    """
    Execute an adaptive scan using an inter-run recommendation engine.

    Parameters
    ----------
    dets : List[OphydObj]
       The detector to read at each point.  The dependent keys that the
       recommendation engine is looking for must be provided by these
       devices.

    first_point : tuple[float, int, int]
       The first point of the scan.  These values will be passed to the
       forward function and the objects passed in real_motors will be moved.

       The order is (Ti_frac, temperature, annealing_time)

    to_recommender : Callable[document_name: str, document: dict]
       This is the callback that will be registered to the RunEngine.

       The expected contract is for each event it will place either a
       dict mapping independent variable to recommended value or None.

       This plan will either move to the new position and take data
       if the value is a dict or end the run if `None`

    from_recommender : Queue
       The consumer side of the Queue that the recommendation engine is
       putting the recommendations onto.

    md : dict[str, Any], optional
       Any extra meta-data to put in the Start document

    take_reading : plan
        function to do the actual acquisition ::

           def take_reading(dets, md={}):
                yield from ...

        Callable[List[OphydObj], Optional[Dict[str, Any]]] -> Generator[Msg]

        This plan must generate exactly 1 Run

        Defaults to `bluesky.plans.count`

    transform_pair : TransformPair

       Expected to have two attributes 'forward' and 'inverse'

       The forward transforms from "data coordinates" (Ti fraction,
       temperature, annealing time) to "beam line" (x/y motor
       position) coordinates ::

          def forward(Ti, temperature, time):
               return x, y

       The inverse transforms from "beam line" (x/y motor position)
       coordinates to "data coordinates" (Ti fraction, temperature,
       annealing time) ::

          def inverse(x, y):
               return Ti_frac, temperature, annealing_time

    snap_function : Callable, optional
        "snaps" the requested measurement to the nearest available point ::

           def snap(Ti, temperature, time):
               returns snapped_Ti, snapped_temperature, snapped_time

    reccomender_timeout : float, optional

        How long to wait for the reccomender to respond before giving
        it up for dead.

    """

    # unpack the real motors
    x_motor, y_motor = real_motors
    # make the soft pseudo axis
    ctrl = Control(name="ctrl")
    pseudo_axes = tuple(getattr(ctrl, k) for k in ctrl.component_names)
    # convert the first_point variable to from we will be getting from
    # queue
    first_point = {m.name: v for m, v in zip(pseudo_axes, first_point)}

    _md = {"batch_id": str(uuid.uuid4())}

    _md.update(md or {})

    @bpp.subs_decorator(to_recommender)
    def gp_inner_plan():
        # drain the queue in case there is anything left over from a previous
        # run
        while True:
            try:
                from_recommender.get(block=False)
            except Empty:
                break
        uids = []
        next_point = first_point
        for j in itertools.count():
            # extract the target position as a tuple
            target = tuple(next_point[k.name] for k in pseudo_axes)
            # if we have a snapping function use it
            if snap_function is not None:
                target = snap_function(*target)
            # compute the real target
            real_target = transform_pair.forward(*target)

            # move to the new position
            target = {m: v for m, v in zip(real_motors, real_target)}
            motor_position_pairs = itertools.chain(*target.items())
            yield from bps.mov(*motor_position_pairs)

            # read back where the motors really are
            real_x = yield from read_the_first_key(x_motor)
            real_y = yield from read_the_first_key(y_motor)

            # compute the new (actual) pseudo positions
            pseudo_target = transform_pair.inverse(real_x, real_y)
            # and set our local synthetic object to them
            yield from bps.mv(*itertools.chain(*zip(pseudo_axes, pseudo_target)))

            # kick off the next actually measurement!
            uid = yield from take_reading(
                dets + list(real_motors) + [ctrl], md={**_md, "batch_count": j}
            )
            uids.append(uid)

            # ask the reccomender what to do next
            next_point = from_recommender.get(timeout=reccomender_timeout)
            if next_point is None:
                return

        return uids

    return (yield from gp_inner_plan())


single_data = [
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
        strip_center=-5,
    ),
    StripInfo(
        temperature=340,
        annealing_time=3600,
        ti_fractions=[16, 18, 22, 25, 29, 34, 36, 43, 49, 53, 58, 62, 67],
        start_position=9.5,
        strip_center=-10,
    ),
    StripInfo(
        temperature=400,
        annealing_time=450,
        ti_fractions=[17, 20, 23, 27, 31, 36, 41, 46, 51, 56, 61, 65, 69],
        start_position=9.5,
        strip_center=-15,
    ),
    StripInfo(
        temperature=400,
        annealing_time=1800,
        ti_fractions=[20, 23, 27, 32, 37, 42, 47, 51, 57, 63, 67, 71, 75, 78, 81],
        start_position=5,
        strip_center=-20,
    ),
    StripInfo(
        temperature=400,
        annealing_time=3600,
        ti_fractions=[19, 22, 25, 30, 35, 39, 45, 50, 55, 60, 65, 69, 73, 77, 79],
        start_position=5,
        strip_center=-25,
    ),
    StripInfo(
        temperature=460,
        annealing_time=450,
        ti_fractions=[17, 20, 24, 28, 32, 37, 43, 48, 52, 58, 63, 67, 71, 75, 78],
        start_position=5,
        strip_center=-30,
    ),
    StripInfo(
        temperature=460,
        annealing_time=15 * 60,
        ti_fractions=[17, 19, 22, 26, 31, 35, 40, 46, 51, 56, 61, 65, 69, 73, 76],
        start_position=5,
        strip_center=-35,
    ),
    StripInfo(
        temperature=460,
        annealing_time=30 * 60,
        ti_fractions=[15, 18, 21, 25, 28, 33, 38, 43, 48, 53, 58, 63, 67, 71, 75],
        start_position=5,
        strip_center=-40,
    ),
]


class SignalWithUnits(Signal):
    def __init__(self, *args, units, **kwargs):
        super().__init__(*args, **kwargs)
        self._units = units

    def describe(self):
        ret = super().describe()
        ret[self.name]["units"] = self._units
        ret[self.name]["source"] = "derived"
        return ret


class Control(Device):
    Ti = Cpt(SignalWithUnits, value=0, units="percent TI", kind="hinted")
    temp = Cpt(SignalWithUnits, value=0, units="degrees C", kind="hinted")
    anneal_time = Cpt(SignalWithUnits, value=0, units="s", kind="hinted")


def read_the_first_key(obj):
    reading = yield from bps.read(obj)
    if reading is None:
        return None
    hints = obj.hints.get("fields", [])
    if len(hints):
        key, *_ = hints
    else:
        key, *_ = list(reading)
    return reading[key]["value"]


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
