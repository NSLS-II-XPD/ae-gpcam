from ophyd import Device, Signal, Component as Cpt


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
