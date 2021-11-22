#! /usr/bin/bash
set -e
set -o xtrace

podman run --pod acquisition --rm -ti -v `pwd`/bluesky_config/scripts:'/app' -w '/app' bluesky /root/.conda/envs/gpcam/bin/python adaptive_gpcam_consumer.py
