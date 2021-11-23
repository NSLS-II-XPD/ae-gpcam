from ae_gpcam.sample_geometry import snap_factory, strip_list_transform_factory
from ae_gpcam.plans import deconstructed_pseudo_plan, stepping_ct
from ae_gpcam.soft_devices import Control

pair = strip_list_transform_factory(single_data)
# snap_function = snap_factory(single_data, time_tol=5, temp_tol=10, Ti_tol=None)
snap_function = snap_factory(single_data, time_tol=None, temp_tol=None, Ti_tol=None)

xrun(
    10,
    deconstructed_pseudo_plan(
        [pe2c],
        point=(18, 400, 7.5 * 60, 1),
        real_motors=(sample_x, ss_stg2_y),
        transform_pair=pair,
        snap_function=snap_function,
        take_data=stepping_ct,
        exposure=20,
        rocking_range=0.5,
        num=3,
        pseudo_signals=Control(name="ctrl"),
    ),
    # print
    # lambda name, doc: pprint.pprint(doc) if name == 'start' else None
)
