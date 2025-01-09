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
    sudo mkdir -p /etc/apt/keyrings
    sudo curl -fsSL https://packages.broadcom.com/artifactory/api/security/keypair/SaltProjectKey/public | sudo tee /etc/apt/keyrings/salt-archive-keyring.pgp
    curl -fsSL https://github.com/saltstack/salt-install-guide/releases/latest/download/salt.sources | sudo tee /etc/apt/sources.list.d/salt.sources
    sudo apt-get update
    sudo apt-get install -y salt-master
    echo "Salt Master installed."
fi

# Ensure Salt Master is running
if ! systemctl is-active --quiet salt-master; then
    echo "Salt Master is not running. Starting now..."
    sudo systemctl enable salt-master && sudo systemctl start salt-master
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


if [ ! -d /srv/salt ]; then
    sudo mkdir -p /srv/salt
    echo "/srv/salt directory created."
fi

# Example to create ipaddr.txt
if [ ! -f /srv/salt/ipaddr.txt ]; then
    sudo cp /home/ubuntu/ipaddr.txt /srv/salt/ipaddr.txt
    echo "Created /srv/salt/ipaddr.txt"
fi

# Define a temporary sudoers file
SUDOERS_TMP=$(mktemp /tmp/sudoers.XXXXXX)
# Copy the current sudoers file to the temporary file
sudo cp /etc/sudoers $SUDOERS_TMP

# Modify the temporary file with sed
if ! grep -q $'Defaults\tenv_reset, !env_reset' $SUDOERS_TMP; then
    sudo sed -i $'s/Defaults\tenv_reset/Defaults\tenv_reset, \!env_reset/g' $SUDOERS_TMP
    echo "Successfully Replaced"
fi

# Validate the modified sudoers file
sudo visudo -c -f $SUDOERS_TMP

# If validation is successful, replace the original sudoers file
if [ $? -eq 0 ]; then
    sudo cp $SUDOERS_TMP /etc/sudoers
    echo "Successfully updated /etc/sudoers"
else
    echo "Error in $SUDOERS_TMP. Check the file for issues."
fi

# Clean up temporary file
sudo rm $SUDOERS_TMP

#Add users root lines of code in the file
addlines="User=root\nGroup=salt\nCacheDirectory=salt/master\nRuntimeDirectory=salt\nStateDirectory=salt/pki/master" 
if ! grep -q 'User=root' /lib/systemd/system/salt-master.service; then
        sudo sed -ie "/^ExecStart/a $addlines" /lib/systemd/system/salt-master.service
        echo "Successfully updated /lib/systemd/system/salt-master.service"
        sudo systemstl daemon-reload
fi

if sudo grep file_recv /etc/salt/master; then
    sudo sed -i 's/#file_recv: False/file_recv: True/g' /etc/salt/master
    sudo sed -i 's/#file_recv_max_size: 100/file_recv_max_size: 100/g' /etc/salt/master
fi

if sudo grep 'user: salt' /etc/salt/master; then
    sudo sed -i 's/user: salt/user: root/g' /etc/salt/master
fi
 
if sudo grep '#file_roots' /etc/salt/master; then
    sudo sed -i '/^#file_roots:/ ,+2 s/^#//' /etc/salt/master
fi

if sudo grep 'interface: 0.0.0.0' /etc/salt/master; then
    # Loop until there are at least three IP addresses
    while true; do
        ip_count=$(hostname -I | awk '{print NF}')
        if [ "$ip_count" -eq 3 ]; then
            break
        fi
        sleep 1
    done
    ip_address=$(hostname -I | awk '{print $2}')
    sudo sed -i "s/#interface: 0.0.0.0/interface: $ip_address/g" /etc/salt/master
fi

sudo systemctl daemon-reload
sudo systemctl restart salt-master

# Install Salt Python client
if ! sudo python3 -c "import salt.client" &> /dev/null; then
    echo "Salt Python client is not installed. Installing now..."
    sudo apt-get install -y python3-pip python3-m2crypto python3-zmq python3.12-venv
    sudo rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED
    python3 -m venv /home/ubuntu/myenv
    source /home/ubuntu/myenv/bin/activate
    python3 -m pip install salt
    sudo chown -R ubuntu:ubuntu myenv/
    pip3 install boto3
    echo "Salt Python client and boto3 installed for user."
fi

# Check if Grafana is installed
if ! command -v grafana-server &> /dev/null; then
	#tutorial - https://youtu.be/d5bNTgaLhmc?si=Q-C0P1JdKGV8AS_x
	#Update ubuntu
	sudo apt-get update -y

	#Install necessary pacakges
	sudo apt-get install wget curl gnupg2 apt-transport-https software-properties-common -y

	#Add gpg key
	wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

	#updo repo list of ubuntu
	echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list

	#refresh and update apt-get
	sudo apt-get update -y

	#Install Grafana 
	sudo apt-get install grafana -y
	echo "Grafana is installed successfully."
else
	echo "Grafana is already installed."
fi

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
	sudo apt-get install nginx -y
    echo "Nginx is installed successfully."
else
    echo "Nginx installed."
fi

echo 'server {
        server_name enter-your-ec2-dnsnamehere;
        listen 80;
        access_log /var/log/nginx/grafana.log;

        location / {
                proxy_pass http://localhost:3000;
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-Host $host:$server_port;
                proxy_set_header X-Forwarded-Server $host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
}' | sudo tee /etc/nginx/conf.d/grafana.conf > /dev/null

# Test Nginx configuration
if sudo nginx -t; then
    echo "Nginx configuration is valid."
else
    echo "Nginx configuration is invalid."
    exit 1
fi

#restart ngix
sudo systemctl restart nginx
