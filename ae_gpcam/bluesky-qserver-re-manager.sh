#!/bin/bash
set -e
source /opt/conda/etc/profile.d/conda.sh
source /etc/bsui/default_vars
source ~/.bashrc
conda activate ae_gpcam
export PYEPICS_LIBCA=/opt/envs/ae_gpcam/epics/lib/linux-x86_64/libca.so
start-re-manager \
  --startup-dir /home/vagrant/miniconda3/envs/ae_gpcam/lib/python3.8/site-packages/bluesky-queueserver \
  --redis-addr localhost:60615 \
  --zmq-publish-console ON \
  --console-output OFF \  # ON is useful when troubleshooting in a terminal
  --keep-re               # don't use this with the demonstration startup scripts
