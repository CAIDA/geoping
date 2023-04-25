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

    # create the salt config file on minion; we need to start/restart it after writing the config file
    sudo echo -e "master: 100.73.84.169" | sudo tee /etc/salt/minion.d/master.conf
    sudo echo -e "ipv6: false" | sudo tee /etc/salt/minion.d/network.conf
    sudo systemctl enable salt-minion && sudo systemctl start salt-minion
fi

if ! systemctl is-active --quiet salt-minion; then
    echo "Salt Minion is not running. Starting now..."
    sudo systemctl enable salt-minion && sudo systemctl start salt-minion
fi

# bring up the instance to the VPN network
sudo netbird up --setup-key "$2"

