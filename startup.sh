#!/bin/bash

if [ "$(hostname)" != "$1" ]; then
    # set the hostname
    sudo hostnamectl set-hostname "$1"
    sudo systemctl restart systemd-hostnamed
    echo "Hostname is set to $1."
else
    echo "Hostname is already $1."
fi

if dpkg -s netbird >/dev/null 2>&1; then
    echo "netbird is already installed."
else
    # install netbird
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg -y
    curl -sSL https://pkgs.wiretrustee.com/debian/public.key | sudo gpg --dearmor --output /usr/share/keyrings/wiretrustee-archive-keyring.gpg
    echo 'deb [signed-by=/usr/share/keyrings/wiretrustee-archive-keyring.gpg] https://pkgs.wiretrustee.com/debian stable main' | sudo tee /etc/apt/sources.list.d/wiretrustee.list
    sudo apt-get update
    sudo apt-get install -y netbird
    echo "netbird installed."
fi

if ! [ -x "$(command -v salt-minion)" ]; then
    echo "Salt Minion is not installed. Installing now..."
    sudo curl -fsSL -o /etc/apt/keyrings/salt-archive-keyring.gpg https://repo.saltproject.io/salt/py3/ubuntu/22.04/amd64/SALT-PROJECT-GPG-PUBKEY-2023.gpg
    echo "deb [signed-by=/etc/apt/keyrings/salt-archive-keyring.gpg arch=amd64] https://repo.saltproject.io/salt/py3/ubuntu/22.04/amd64/latest jammy main" | sudo tee /etc/apt/sources.list.d/salt.list
    sudo apt-get update
    sudo apt-get install -y salt-minion

    # # #Code to update a master
    # sudo echo -e "master: 100.73.241.194" | sudo tee /etc/salt/minion.d/master.conf
    # sudo rm /etc/salt/pki/minion/minion_master.pub
    # sudo systemctl restart salt-minion.service
    
    # create the salt config file on minion; we need to start/restart it after writing the config file
    sudo echo -e "master: 100.73.241.194" | sudo tee /etc/salt/minion.d/master.conf
    sudo echo -e "ipv6: false" | sudo tee /etc/salt/minion.d/network.conf
    sudo echo -e "id: $1" | sudo tee /etc/salt/minion.d/minion.conf
    
    sudo systemctl enable salt-minion && sudo systemctl start salt-minion
    # restart the service to get the config changes
    echo "Restarting salt-minion.service..."
    sudo systemctl restart salt-minion.service
fi

if ! systemctl is-active --quiet salt-minion; then
    echo "Salt Minion is not running. Starting now..."
    sudo systemctl enable salt-minion && sudo systemctl start salt-minion
fi

if ! command -v scamper &> /dev/null; then
    echo "Scamper is not installed. Installing scamper..."
    sudo apt install -y build-essential 
    sudo rm -rf /home/ubuntu/scamper*
    sudo add-apt-repository -y ppa:matthewluckie/scamper
    sudo apt update
    sudo apt install -y scamper
    sudo apt install -y scamper-utils
else
    sudo apt update
    sudo apt install --only-upgrade -y scamper
    sudo apt install --only-upgrade -y scamper-utils
fi

# Check if bzip2 is installed
if ! command -v bzip2 &> /dev/null; then
    echo "bzip2 is not installed. Installing now..."
    sudo apt-get install -y bzip2
fi

# bring up the instance to the VPN network
sudo netbird up --setup-key "$2"


