"""Data and bound plan for SBU sample geometry."""

from dataclasses import asdict, astuple

import numpy as np

import scipy.stats


import matplotlib.patches as mpatches

# These terms match the pseudo positioner code in ophyd and are standard
# in motion control.

# Forward: pseudo positions -> real positions
#     aka: data coordinates -> beamline coordinates
# Inverse: real positions       -> pseudo positions
#     aka: beamline coordinates -> data coordinates
from ae_gpcam.sample_geometry import (
    StripInfo,
    strip_list_transform_factory,
    single_strip_transform_factory,
    show_layout,
    snap_factory,
)
from ae_gpcam.plans import deconstructed_pseudo_plan
from ae_gpcam.soft_devices import Control


# this is to do the data-entry on the temperature, annealing time,
# start distance, and ti_fraction gradient.
_layout_template = [
    StripInfo(
        temperature=340,
        annealing_time=450,
        ti_fractions=[19, 22, 27, 30, 35, 40, 44, 49, 53],
        start_distance=-13.5,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=340,
        annealing_time=1800,
        ti_fractions=[19, 20, 23, 28, 32, 37, 42, 46, 51, 56, 60],
        start_distance=-9.0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=340,
        annealing_time=3600,
        ti_fractions=[16, 18, 22, 25, 29, 34, 36, 43, 49, 53, 58, 62, 67],
        start_distance=-4.5,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=400,
        annealing_time=450,
        ti_fractions=[17, 20, 23, 27, 31, 36, 41, 46, 51, 56, 61, 65, 69],
        start_distance=-4.5,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=400,
        annealing_time=1800,
        ti_fractions=[20, 23, 27, 32, 37, 42, 47, 51, 57, 63, 67, 71, 75, 78, 81],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=400,
        annealing_time=3600,
        ti_fractions=[19, 22, 25, 30, 35, 39, 45, 50, 55, 60, 65, 69, 73, 77, 79],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=460,
        annealing_time=450,
        ti_fractions=[17, 20, 24, 28, 32, 37, 43, 48, 52, 58, 63, 67, 71, 75, 78],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=460,
        annealing_time=15 * 60,
        ti_fractions=[17, 19, 22, 26, 31, 35, 40, 46, 51, 56, 61, 65, 69, 73, 76],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=460,
        annealing_time=30 * 60,
        ti_fractions=[15, 18, 21, 25, 28, 33, 38, 43, 48, 53, 58, 63, 67, 71, 75],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=340,
        annealing_time=1800,
        ti_fractions=[19, 20, 23, 28, 32, 37, 42, 46, 51, 56, 60],
        start_distance=-9.0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=340,
        annealing_time=3600,
        ti_fractions=[16, 18, 22, 25, 29, 34, 36, 43, 49, 53, 58, 62, 67],
        start_distance=-4.5,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=400,
        annealing_time=450,
        ti_fractions=[17, 20, 23, 27, 31, 36, 41, 46, 51, 56, 61, 65, 69],
        start_distance=-4.5,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=400,
        annealing_time=1800,
        ti_fractions=[20, 23, 27, 32, 37, 42, 47, 51, 57, 63, 67, 71, 75, 78, 81],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=400,
        annealing_time=3600,
        ti_fractions=[19, 22, 25, 30, 35, 39, 45, 50, 55, 60, 65, 69, 73, 77, 79],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=460,
        annealing_time=450,
        ti_fractions=[17, 20, 24, 28, 32, 37, 43, 48, 52, 58, 63, 67, 71, 75, 78],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=460,
        annealing_time=15 * 60,
        ti_fractions=[17, 19, 22, 26, 31, 35, 40, 46, 51, 56, 61, 65, 69, 73, 76],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
    StripInfo(
        temperature=460,
        annealing_time=30 * 60,
        ti_fractions=[15, 18, 21, 25, 28, 33, 38, 43, 48, 53, 58, 63, 67, 71, 75],
        start_distance=0,
        reference_y=0,
        reference_x=5,
        angle=0,
        thickness=-1,
    ),
]


# data collected on the first day for the as-mounted centers of the strips at 3 positions.
mpos = np.array(
    [
        sorted([float(__.strip()) for __ in _.split(";")])
        for _ in """83.97; 79.98; 74.96; 70.1; 64.65; 60.04; 55.62; 51.09; 41.55; 36.62; 31.59; 26.99; 21.88; 17.62; 12.43; 7.92; 3.4
3.28; 8.01; 12.69; 17.62; 22.4; 27.33; 31.85; 36.7; 41.64; 51.68; 56.55; 61.06; 65.67; 70.43; 75.2; 80.58; 84.49
3.67; 7.9; 13.19; 17.8; 22.5; 27.5; 32.03; 36.41;41.5; 52.46; 57.05; 61.75; 66.52; 70.52; 75.31;80.82; 84.47""".split(
            "\n"
        )
    ]
).T
sampled_x = [35, 60, 85]

# fit the above to a line
fits = [scipy.stats.linregress(sampled_x, m) for m in mpos]
# get the 0 we need to make the start_distance's above make sense
ref_x = 95 - 1.25

# generate the data by zipping the template + the fit angle and offsets
single_data = [
    StripInfo(**{**asdict(strip), **measured, "thickness": thickness})
    for strip, measured, thickness in zip(
        _layout_template,
        [
            {
                "angle": np.arctan2(f.slope, 1),
                "reference_x": ref_x,
                "reference_y": ref_x * f.slope + f.intercept,
            }
            for f in fits
        ],
        [0] * 9 + [1] * 8,
    )
]


def show_current_config():
    """Helper function to us locals to show current configuration."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    show_layout(single_data, ax=ax)

    ax.plot(sampled_x, mpos.T, marker="o", color=".5")

    ax.add_patch(
        mpatches.Rectangle((95 - 64, 2.5), 64, 80, color="k", alpha=0.25, zorder=2)
    )
    plt.show()


# This is a run-time test
for strip in single_data:
    pair = single_strip_transform_factory(*astuple(strip))
    for j, ti_frac in enumerate(strip.ti_fractions[1:-1]):
        start = (ti_frac, strip.temperature, strip.annealing_time, strip.thickness)
        x, y = pair.forward(
            ti_frac, strip.temperature, strip.annealing_time, strip.thickness
        )
        ret = pair.inverse(np.round(x, 2), y)
        assert np.allclose(start, ret, atol=0.01)

pair = strip_list_transform_factory(single_data)
snap_function = snap_factory(single_data, time_tol=None, temp_tol=None, Ti_tol=None)


def SBU_plan(
    ti_fraction: float,
    temperature: int,
    annealing_time: int,
    exposure: float,
    thickness: int,
    num: int,
    *,
    rocking_range: float = 2,
):
    ctrl = Control(name="ctrl")
    return (
        yield from (
            deconstructed_pseudo_plan(
                [pe2c],
                point=(ti_fraction, temperature, annealing_time, thickness),
                exposure=exposure,
                num=num,
                rocking_range=rocking_range,
                transform_pair=pair,
                real_motors=(sample_x, ss_stg2_y),
                pseudo_signals=ctrl,
                snap_function=snap_function,
            )
        )
    )
