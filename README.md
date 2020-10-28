# ae-gpcam
Autonomous experiment at XPD using gpCAM.

This repository is largely a copy of https://github.com/bluesky/bluesky-pods.
These files have been added:
 * ae-gpcam/Vagrantfile
 * ae-gpcam/bluesky_config/scripts/analysis_consumer.py
 * ae-gpcam/launchers/start_analysis_server.sh

These files have been modified:
 * ae-gpcam/start_acquisition_pod.sh
 * ae-gpcam/bluesky_config/scripts/adaptive_consumer.py
 * ae-gpcam/bluesky_config/ipython/profile_default/startup/00-base.py

The autonomous experiment uses three processes:
 * bluesky
 * xpdan
 * adaptive server

These processes communicate using Zero MQ (0MQ) and Redis:
```
  RE -----> 0MQ -----> xpdan -----> 0MQ -----> adaptive_server
  ^                                               |
  | <--------- redis <-----<-----<-----<-----<----|
```

The script `analysis_server.py` is provided to simulate xpdan by simply forwarding documents from the RunEngine to the adaptive server.

### Run in a VM

An easy way to run all three processes is from within a Vagrant VM.
A `Vagrantfile` is provided that installs podman and related prerequisites on CentOS 8.
Once Vagrant and VirtualBox are installed on the host computer and this repository has been cloned, build a VM:
```
cd ae-gpcam
vagrant up
```
Podman images will be created the first time the VM starts.

Open a terminal and SSH into the VM.
Change to the shared repository directory.
Then start the acquisition pod.
```
vagrant ssh
cd /vagrant/ae_gpcam
sudo bash start_acquisition_pod.sh
```

Start the analysis server (analogous to xpdan) from inside the VM:
```
sudo bash launchers/start_analysis_server.sh
++ pwd
+ podman run --pod acquisition --rm -ti -v /vagrant/ae_gpcam/bluesky_config/scripts:/app -w /app bluesky python3 analysis_consumer.py
ANALYSIS CONSUMER IS LISTENING ON b'from-RE'
```

Open a new terminal and start the adaptive server from inside the VM:
```
vagrant ssh
cd /vagrant/ae_gpcam
sudo bash launchers/start_adaptive_server.sh
++ pwd
+ podman run --pod acquisition --rm -ti -v /vagrant/ae_gpcam/bluesky_config/scripts:/app -w /app bluesky python3 adaptive_consumer.py
ADAPTIVE CONSUMER LISTENING ON b'from-analysis
```

Open a new terminal, start bluesky from inside the VM, and run an adaptive plan:
```
vagrant ssh
cd /vagrant/ae_gpcam
sudo bash launch_bluesky_headless.sh
+ '[' '' '!=' '' ']'
+ imagename=bluesky
++ pwd
+ podman run --pod acquisition -ti --rm -v /vagrant/ae_gpcam:/app -w /app -v ./bluesky_config/ipython:/usr/local/share/ipython -v ./bluesky_config/databroker:/usr/local/share/intake -v ./bluesky_config/happi:/usr/local/share/happi -e EPICS_CA_ADDR_LIST=10.0.2.255 -e EPICS_CA_AUTO_ADDR_LIST=no bluesky ipython3 --ipython-dir=/usr/local/share/ipython
Python 3.8.6 (default, Sep 25 2020, 00:00:00)
Type 'copyright', 'credits' or 'license' for more information
IPython 7.12.0 -- An enhanced Interactive Python. Type '?' for help.

In [1]: from ophyd.sim import *

In [2]: from bluesky_adaptive.per_start import adaptive_plan

In [3]: RE(adaptive_plan([det], {motor: 0}, to_recommender=None, from_recommender=from_recommender))
```

