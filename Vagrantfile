Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-20.10"
  config.vm.box_check_update = true

  config.vm.network "forwarded_port", guest: 60610, host: 60610

  config.ssh.forward_agent = true
  config.ssh.forward_x11 = true

  config.vm.provider "virtualbox" do |vb|
    vb.gui = false
  end

  # Enable provisioning with a shell script. Additional provisioners such as
  # Ansible, Chef, Docker, Puppet and Salt are also available. Please see the
  # documentation for more information about their specific syntax and use.
  #config.vm.provision "file", source: "~/.ssh/id_rsa.pub", destination: "/home/vagrant/.ssh/id_rsa.pub"
  #config.vm.provision "file", source: "~/.ssh/id_rsa", destination: "/home/vagrant/.ssh/id_rsa"
#   config.vm.provision "shell", inline: <<-SHELL
#     sudo echo -e "\nX11UseLocalhost no" >> /etc/ssh/sshd_config
#     sudo dnf -y update
#     sudo dnf -y install gcc git podman buildah python38 python38-devel python38-pip
#   SHELL

  config.vm.provision "shell", inline: <<-SHELL
    # https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04
    apt update
    apt full-upgrade
    apt install -y python3-pip
    # install X11 for matplotlib
    apt install -y xserver-xorg-core x11-utils x11-apps

    # install miniconda3
    wget -P /tmp https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash /tmp/Miniconda3-latest-Linux-x86_64.sh -b -p /home/vagrant/miniconda3
    rm /tmp/Miniconda3-latest-Linux-x86_64.sh
    /home/vagrant/miniconda3/bin/conda init --system
    /home/vagrant/miniconda3/bin/conda update conda -y

    # create a conda environment for development
    /home/vagrant/miniconda3/bin/conda create -y -n ae_gpcam python=3.8 bluesky-httpserver
    /home/vagrant/miniconda3/envs/ae_gpcam/bin/pip install -e /vagrant
    /home/vagrant/miniconda3/envs/ae_gpcam/bin/pip install -r /vagrant/requirements-dev.txt
    # change ownership for /home/vagrant/miniconda3 after creating virtual environments and installing packages
    chown -R vagrant:vagrant /home/vagrant/miniconda3

    # install mongodb
    wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
    apt update
    apt install -y mongodb-org

    # note: change the mongodb bindIP in /etc/mongod.conf to 0.0.0.0 to allow connections from the host
    sed "s;bindIP;bindIP 0.0.0.0;" -i /etc/mongod.conf

    systemctl start mongod
    systemctl enable mongod

    # databroker will look for this directory
    # it should probably be created in scripts/start_sirepo.sh
    cd /home/vagrant
    mkdir -p .local/share/intake
    chown -Rv vagrant:vagrant .local
  SHELL
end
