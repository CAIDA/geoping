#!/usr/bin/env python3

import salt.client
from datetime import datetime
import json
import os
import shutil
import argparse
import boto3
from botocore.exceptions import NoCredentialsError

# Define the argument parser and parse it
parser = argparse.ArgumentParser()
parser.add_argument("--regex", type=str, default="aws-us-east-2*", help="regex for targeted vantage points")
parser.add_argument("--launch", type=str, default="ping", help="Options to launch the experiment, ping = icmp-echo ping, ping-tcp = tcp ping, trace = traceroute")
parser.add_argument("--flags", type=str, default="", help="add the flags you want to conduct complex tests")
args = parser.parse_args()

############### PARAMETERS ###########
TARGET = args.regex
IP_ADDRESS_LIST_FILENAME = 'ipaddr.txt'
SCAMPER_PORT = 5001
SCAMPER_PPS = 1500
SC_PINGER_LOG_FILEAME = "ping.log"
SC_ATTACH_LOG_FILEAME = "traceroute.log"
GEOPING_RESULTS_DIR = "/home/ubuntu/geoping-results"
BUCKET = 'geoping-results'
CHUNK_SIZE = 25
######################################

# Instantiate a Client
local_client = salt.client.LocalClient()

# Create a measurement ID for unique identification of results
DATE = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
RESULT_FILE_NAME = "geoloc-pinger_{}.{}.warts".format(args.launch, DATE)
print("Measurement ID: {}\n".format(RESULT_FILE_NAME))
MINION_IP_ADDRESS_LIST_FILENAME = 'ipaddr_{}.txt'.format(DATE)
CMD_REMOVE_AND_CREATE_IP_ADDR_FILE = f"sudo rm /home/ubuntu/{MINION_IP_ADDRESS_LIST_FILENAME}*; echo 'Deleted all previous IP files'"
CMD_CREATE_RESULTS_DIR_IF_NOT_EXISTS = f"sudo mkdir -p {GEOPING_RESULTS_DIR} && echo 'Created {GEOPING_RESULTS_DIR} directory if it did not exist'"
CMD_REMOVE_RESULTS_DIR = f"sudo rm -rf {GEOPING_RESULTS_DIR}"
CMD_SPLIT_FILE = f"split -l {CHUNK_SIZE} /home/ubuntu/{MINION_IP_ADDRESS_LIST_FILENAME} /home/ubuntu/{MINION_IP_ADDRESS_LIST_FILENAME}_"
CMD_RENAME_FILE = f'counter=0; for i in $(ls -1 /home/ubuntu/{MINION_IP_ADDRESS_LIST_FILENAME}_*); do sudo mv "$i" "/home/ubuntu/{MINION_IP_ADDRESS_LIST_FILENAME}_$counter.txt"; counter=$((counter + 1)); done ; echo "Splitted and renamed all ip file chunks"'
CMD_KILL_SCAMPER = f"sudo kill -9 $(sudo lsof -ti :{SCAMPER_PORT}) 2>/dev/null && echo 'Killed process (if any) on port {SCAMPER_PORT}'"
CMD_START_SCAMPER = f"sudo scamper -P {SCAMPER_PORT} -p {SCAMPER_PPS} -D && echo 'Started scamper on port {SCAMPER_PORT}' && sleep 1"
CMD_AGGREGATE_CHUNK_RESULTS = f"sudo sc_wartscat -o {GEOPING_RESULTS_DIR}/{RESULT_FILE_NAME} {GEOPING_RESULTS_DIR}/geoloc-pinger_{args.launch}.{DATE}_*.warts"
CMD_COMPRESS_RESULT_FILE = f"bzip2 -9 -f {GEOPING_RESULTS_DIR}/{RESULT_FILE_NAME} && echo 'Compressed result file'"
COMPRESSED_RESULT_FILENAME = RESULT_FILE_NAME + '.bz2'
COMPRESSED_RESULT_FILEPATH = GEOPING_RESULTS_DIR + '/' + COMPRESSED_RESULT_FILENAME

# Copy the IP addresses list file to minions
print("Copying IP address list file to minions...")
result = local_client.cmd(TARGET, 'cp.get_file', ['salt://' + IP_ADDRESS_LIST_FILENAME, '/home/ubuntu/' + MINION_IP_ADDRESS_LIST_FILENAME])
print("Results of copying ip address list file to all minions")
print(json.dumps(result, indent=4))
print()

#Delete and recreate geoping-results directory
print("Creating a new results directory of doesn't exist...")
result = local_client.cmd(TARGET, "cmd.run", [CMD_CREATE_RESULTS_DIR_IF_NOT_EXISTS])
print(json.dumps(result, indent=4))
print()

# Split the IP address file and rename the split files
print(f"Splitting IP address file into chunks of {CHUNK_SIZE} lines each and renaming them...")
command = "&&".join([CMD_SPLIT_FILE, CMD_RENAME_FILE])
result = local_client.cmd(TARGET, "cmd.run", [command], shell=True)
print(json.dumps(result, indent=4))
print()

# Prepare and start the Scamper process on the minions and run sc_attach on the minions
print("Running Scamper on each IP address chunk and attaching results...")
command = f"""
counter=0
for ips in $(ls -1 /home/ubuntu/{MINION_IP_ADDRESS_LIST_FILENAME}_*); do
    {CMD_KILL_SCAMPER}
    {CMD_START_SCAMPER}
    sudo sc_attach -c 'trace {args.flags}' -i $ips -o {GEOPING_RESULTS_DIR}/geoloc-pinger_{args.launch}.{DATE}_$counter.warts -p {SCAMPER_PORT}
    counter=$((counter + 1))
done
"""
result = local_client.cmd(TARGET, "cmd.run", [command], shell=True)
print("Done Running sc_attach")
print(json.dumps(result, indent=4))
print()

# Run sc_wartscat to aggregate the results
print("Aggregating all chunks results with sc_wartscat...")
result = local_client.cmd(TARGET, "cmd.run", [CMD_AGGREGATE_CHUNK_RESULTS], shell=True)
print(json.dumps(result, indent=4))
print()

# Compress the aggregated result file
print("Compressing the result file with bzip2...")
result = local_client.cmd(TARGET, "cmd.run", [CMD_COMPRESS_RESULT_FILE], shell=True)
print(json.dumps(result, indent=4))
print()

# Aggregate the results from the minions for this chunk
print("Pulling compressed result files from all minions...")
result = local_client.cmd(TARGET, "cp.push", [COMPRESSED_RESULT_FILEPATH, False, COMPRESSED_RESULT_FILENAME])
print(f"Results of pulling files from all minions")
print(json.dumps(result, indent=4))
print()

# Aggregate all results back in one directory
print("Aggregating results from all minions into one directory on the master...")
minions_cache_dir = '/var/cache/salt/master/minions'
aggregate_results_dir_basename = COMPRESSED_RESULT_FILENAME[:-10]
aggregate_results_dir = os.path.join('/home/ubuntu/aggregate-results', aggregate_results_dir_basename)

print("aggregate results dir base", aggregate_results_dir_basename)
print("aggregate results dir", aggregate_results_dir)

# Get a list of all items in the directory
items = os.listdir(minions_cache_dir)
# Use a list comprehension to filter out non-directories
minions_names = [item for item in items if os.path.isdir(os.path.join(minions_cache_dir, item))]

# Create aggregate results dir if it doesn't exist
if not os.path.exists(aggregate_results_dir):
    os.makedirs(aggregate_results_dir)

for minion in minions_names:
    source_file_path = os.path.join(minions_cache_dir, minion, 'files', COMPRESSED_RESULT_FILENAME)
    if os.path.isfile(source_file_path):
        # If the source file exists, construct the destination path by joining the destination directory path and the filename
        destination_file_path = os.path.join(aggregate_results_dir, minion + '.' + COMPRESSED_RESULT_FILENAME)

        # Copy the source file to the destination file path
        shutil.move(source_file_path, destination_file_path)
print(f"Results have been aggregated into {aggregate_results_dir}")
print()

# Remove any existing IP address files from previous runs on the minions
print("Removing old IP address files from minions...")
result = local_client.cmd(TARGET, "cmd.run", [CMD_REMOVE_AND_CREATE_IP_ADDR_FILE])
print(json.dumps(result, indent=4))
print()

#Delete and recreate geoping-results directory
print("Deleting geoping-results directory and creating a new one...")
result = local_client.cmd(TARGET, "cmd.run", [CMD_REMOVE_RESULTS_DIR])
print(json.dumps(result, indent=4))
print()

# Upload the aggregated results directory to S3
def upload_directory_to_s3(local_directory, bucket_name):
    with open('config.json', 'r') as config:
        credentials = json.load(config)

    s3_client = boto3.client('s3', 
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        region_name="us-east-1")

    for root, dirs, files in os.walk(local_directory):
        dir_path = os.path.basename(local_directory)
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_directory)
            s3_path = os.path.join(dir_path, relative_path).replace("\\", "/")

            try:
                s3_client.upload_file(local_path, bucket_name, s3_path)
                print(f"Successfully uploaded {local_path} to s3://{bucket_name}/{s3_path}")
            except FileNotFoundError:
                print(f"File not found: {local_path}")
            except NoCredentialsError:
                print("Credentials not available")
            except Exception as e:
                print(f"Failed to upload {local_path} to s3://{bucket_name}/{s3_path}: {e}")

upload_directory_to_s3(aggregate_results_dir, BUCKET)


#sudo salt-run jobs.active | sed -n '/Running:/,/StartTime:/p' | sed -e '1d' -e '$d' | awk '/^ *[a-zA-Z]/ { print }' | sed -e 's/^[[:space:]]*//' -e 's/:$//'
