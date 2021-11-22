#! /usr/bin/bash
set -e
set -o xtrace

if [ "$1" != "" ]; then
    imagename=$1
else
    imagename="bluesky"
fi

# add -v /vagrant/TiCu_export for sbu_sim and ae-xpd
podman run --pod acquisition \
       -ti  --rm \
       -v `pwd`:'/app' -w '/app' \
       -v ./bluesky_config/ipython:/usr/local/share/ipython \
       -v ./bluesky_config/databroker:/usr/local/share/intake \
       -v ./bluesky_config/happi:/usr/local/share/happi \
       -v /vagrant/TiCu_export:/usr/local/share/TiCu_export \
       -e EPICS_CA_ADDR_LIST=10.0.2.255 \
       -e EPICS_CA_AUTO_ADDR_LIST=no \
       $imagename \
       ipython3 --ipython-dir=/usr/local/share/ipython
