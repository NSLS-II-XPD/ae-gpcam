from bluesky.run_engine import RunEngine
from xpdacq.xpdacq import CustomizedRunEngine


class XrunStandardSignature(CustomizedRunEngine):
    """
    A sub-class of a sub-class of the RunEngine to restore the signature.

    xpdacq provides a customized RE with a different signature and some built
    in pre-processors / meta-data handling.  To work with the queueserver we
    need to have a RE with the standard signature.

    """

    def __call__(self, plan, *args, **kwargs):
        super().__call__({}, plan, *args, **kwargs)


XrunStandardSignature.__call__.__doc__ = RunEngine.__call__.__doc__
