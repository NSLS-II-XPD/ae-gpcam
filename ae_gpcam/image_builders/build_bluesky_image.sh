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

# install gpcam in a conda environment because numba
# is difficult to install using pip
# assume gpcam repository has been cloned to /vagrant
buildah run $container -- dnf -y install conda
buildah run $container -- conda create --yes --quiet --name gpcam
buildah run $container -- conda install --yes --quiet --name gpcam numba
buildah run $container -- /root/.conda/envs/gpcam/bin/pip install git+https://github.com/bluesky/bluesky-adaptive.git@main#egg=bluesky-adaptive
buildah run -v /vagrant/gpcamv4and5:/usr/local/share/gpcam $container -- /root/.conda/envs/gpcam/bin/pip install -e /usr/local/share/gpcam

buildah run $container -- pip3 uninstall --yes pyepics

buildah unmount $container
buildah commit $container bluesky
