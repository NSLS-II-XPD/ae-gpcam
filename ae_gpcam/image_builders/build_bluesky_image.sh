#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from bluesky-base)
buildah run $container -- pip3 install nslsii
buildah run $container -- pip3 install git+https://github.com/bluesky/bluesky-adaptive.git@main#egg=bluesky-adaptive
buildah run $container -- pip3 install git+https://github.com/bluesky/bluesky-queueserver.git@main#egg=bluesky-queueserver
buildah run $container -- pip3 install git+https://github.com/pcdshub/happi.git@master#egg=happi

# added for ae-xpd
buildah run $container -- pip3 install databroker-pack
buildah run -v /vagrant/TiCu_export:/usr/local/share/TiCu_export $container -- databroker-unpack inplace /usr/local/share/TiCu_export xpd_auto_202003_msgpack
buildah run $container -- pip3 install git+https://github.com/tacaswell/sbu_sim.git@master#egg=sbu_sim

buildah run $container -- pip3 uninstall --yes pyepics

buildah unmount $container
buildah commit $container bluesky
