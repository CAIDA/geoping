#!/bin/bash

# Set the hostname if necessary
if [ "$(hostname)" != "$1" ]; then
    sudo hostnamectl set-hostname "$1"
    sudo systemctl restart systemd-hostnamed
    echo "Hostname is set to $1."
else
    echo "Hostname is already $1."
fi

# Install NetBird if not installed
if dpkg -s netbird >/dev/null 2>&1; then
    echo "NetBird is already installed."
else
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    curl -sSL https://pkgs.wiretrustee.com/debian/public.key | sudo gpg --dearmor --output /usr/share/keyrings/wiretrustee-archive-keyring.gpg
    echo 'deb [signed-by=/usr/share/keyrings/wiretrustee-archive-keyring.gpg] https://pkgs.wiretrustee.com/debian stable main' | sudo tee /etc/apt/sources.list.d/wiretrustee.list
    sudo apt-get update
    sudo apt-get install -y netbird
    echo "NetBird installed."
fi

# Install Salt Master if not installed
if ! [ -x "$(command -v salt-master)" ]; then
    echo "Salt Master is not installed. Installing now..."
    sudo curl -fsSL -o /etc/apt/keyrings/salt-archive-keyring.gpg https://repo.saltproject.io/salt/py3/ubuntu/22.04/amd64/SALT-PROJECT-GPG-PUBKEY-2023.gpg
    echo "deb [signed-by=/etc/apt/keyrings/salt-archive-keyring.gpg arch=amd64] https://repo.saltproject.io/salt/py3/ubuntu/22.04/amd64/latest jammy main" | sudo tee /etc/apt/sources.list.d/salt.list
    sudo apt-get update
    sudo apt-get install -y salt-master
    echo "Salt Master installed."
fi

# Ensure Salt Master is running
if ! systemctl is-active --quiet salt-master; then
    echo "Salt Master is not running. Starting now..."
    sudo systemctl enable salt-master && sudo systemctl start salt-master
fi

## Install Salt Minion if not installed (assuming this script runs on minions as well)
#if ! [ -x "$(command -v salt-minion)" ]; then
#    echo "Salt Minion is not installed. Installing now..."
#    sudo apt-get install -y salt-minion
#    echo "Salt Minion installed."
#fi
#
## Configure Salt Minion to connect to the Salt Master
#sudo sed -i "s/#master: salt/master: $MASTER_HOSTNAME/" /etc/salt/minion
#
## Start and enable Salt Minion service
#sudo systemctl start salt-minion
#sudo systemctl enable salt-minion

# Install Salt Python client
if ! python3 -c "import salt.client" &> /dev/null; then
    echo "Salt Python client is not installed. Installing now..."
    sudo apt-get install -y python3-pip python3-m2crypto python3-zmq
    sudo pip3 install salt
    echo "Salt Python client installed."
fi

# Install AWS CLI if not installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Installing now..."
    sudo apt-get install -y unzip
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -rf awscliv2.zip aws
    echo "AWS CLI installed."
fi

# Install Scamper if not installed
if ! command -v scamper &> /dev/null; then
    echo "Scamper is not installed. Installing now..."
    sudo apt install -y build-essential 
    sudo rm -rf /home/ubuntu/scamper*
    sudo add-apt-repository -y ppa:matthewluckie/scamper
    sudo apt update
    sudo apt install -y scamper
    sudo apt install -y scamper-utils
else
    sudo apt update
    sudo apt install --only-upgrade -y scamper scamper-utils
fi

# Check if bzip2 is installed
if ! command -v bzip2 &> /dev/null; then
    echo "bzip2 is not installed. Installing now..."
    sudo apt-get install -y bzip2
fi

# Bring up the instance to the VPN network
sudo netbird up --setup-key "$2"

echo "Salt Master setup completed."
