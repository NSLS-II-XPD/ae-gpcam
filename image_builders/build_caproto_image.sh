
#! /usr/bin/bash
set -e
set -o xtrace


container=$(buildah from fedora)
buildah run $container -- dnf -y install python3 ipython3 python3-pip python3-numpy python3-netifaces
buildah run $container -- pip3 install caproto[standard]
# this is the thing you want to change to spawn your IOC
buildah config --cmd "python3 -m caproto.ioc_examples.simple --list-pvs" $container
buildah unmount $container
buildah commit $container caproto
