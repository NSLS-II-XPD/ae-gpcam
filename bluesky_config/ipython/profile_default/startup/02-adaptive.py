"""Plan for running pgcam AE with a gradient TiCu sample."""


from ophyd import Device, Signal, Component as Cpt
from ae_gpcam.plans import deconstructed_pseudo_plan


class SignalWithUnits(Signal):
    """Soft signal with units tacked on."""

    def __init__(self, *args, units, **kwargs):
        super().__init__(*args, **kwargs)
        self._units = units

    def describe(self):
        ret = super().describe()
        ret[self.name]["units"] = self._units
        ret[self.name]["source"] = "derived"
        return ret


class Control(Device):
    """Soft device to inject computed pseudo positions."""

    Ti = Cpt(SignalWithUnits, value=0, units="percent TI", kind="hinted")
    temp = Cpt(SignalWithUnits, value=0, units="degrees C", kind="hinted")
    annealing_time = Cpt(SignalWithUnits, value=0, units="s", kind="hinted")
    thickness = Cpt(SignalWithUnits, value=0, units="enum", kind="hinted")


def SBU_plan(
    ti_fraction: float,
    temperature: int,
    annealing_time: int,
    exposure: float,
    num: int,
    *,
    rocking_range: float = 2,
):
    ctrl = Control(name="ctrl")
    return (
        yield from (
            deconstructed_pseudo_plan(
                [pe2c],
                point=(ti_fraction, temperature, annealing_time),
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
