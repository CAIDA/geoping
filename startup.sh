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
    sudo apt-get install ca-certificates curl gnupg -y
    curl -sSL https://pkgs.wiretrustee.com/debian/public.key | sudo gpg --dearmor --output /usr/share/keyrings/wiretrustee-archive-keyring.gpg
    echo 'deb [signed-by=/usr/share/keyrings/wiretrustee-archive-keyring.gpg] https://pkgs.wiretrustee.com/debian stable main' | sudo tee /etc/apt/sources.list.d/wiretrustee.list
    sudo apt-get update
    sudo apt-get install netbird
    echo "netbird installed."
fi

# bring up the instance to the VPN network
sudo netbird up --setup-key "$2"

