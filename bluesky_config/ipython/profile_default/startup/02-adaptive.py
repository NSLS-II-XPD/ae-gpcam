"""Plan for running pgcam AE with a gradient TiCu sample."""


from ae_gpcam.plans import deconstructed_pseudo_plan
from ae_gpcam.soft_devices import Control


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
                real_motors=(),
                pseudo_signals=ctrl,
                snap_function=snap_function,
            )
        )
    )
