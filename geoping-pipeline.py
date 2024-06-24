#!/usr/bin/env python3

import salt.client
from datetime import datetime
import json
import os
import shutil
import argparse

# Define the argument parser and parse it
parser = argparse.ArgumentParser()
parser.add_argument("--regex", type=str, default="aws-us-east-2*", help="regex for targeted vantage points")
parser.add_argument("--launch", type=str, default="ping", help="Options to launch the experiment, ping = icmp-echo ping, ping-tcp = tcp ping, trace = traceroute")
args = parser.parse_args()

############### PARAMETERS ###########
TARGET = args.regex
IP_ADDRESS_LIST_FILENAME =  'ipaddr.txt'#'itdk-run-20230308.addrs.trimmed'
SCAMPER_PORT = 5001
SCAMPER_PPS = 1500
SC_PINGER_LOG_FILEAME = "ping.log"
SC_ATTACH_LOG_FILEAME = "traceroute.log"
GEOPING_RESULTS_DIR = "/home/ubuntu/geoping-results"
######################################


# Instantiate a Client
local_client = salt.client.LocalClient()

# Create Measurement ID
DATE = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
RESULT_FILE_NAME="geoloc-pinger.{}.warts".format(DATE)
print("Measurement ID: {}\n".format(RESULT_FILE_NAME))

# Copy the IP addresses list file to minions
result = local_client.cmd(TARGET, 'cp.get_file', ['salt://' + IP_ADDRESS_LIST_FILENAME, '/home/ubuntu/' + IP_ADDRESS_LIST_FILENAME])
print("Results of copying ip address list file to all minions")
print(json.dumps(result, indent=4))
print()

# Close previous scamper daemon if it was running and start new daemon; Start scamper on minions; Launch sc_pinger experiment
# IMP note: In CMD_KILL_SCAMPER, we get error when we try to kill process that was not running; we want execution of next cmd to continue and hence use ';' to merge cmds
CMD_REMOVE_AND_CREATE_RESULTS_DIR = "sudo rm -rf {}; mkdir {} && echo 'Created {} directory'".format(GEOPING_RESULTS_DIR, GEOPING_RESULTS_DIR, GEOPING_RESULTS_DIR)
CMD_KILL_SCAMPER = "sudo kill -9 `sudo lsof -ti :{}` 2>/dev/null && echo 'Killed process (if any) on port 5001'".format(SCAMPER_PORT, )
CMD_START_SCAMPER = "sudo scamper -P {} -p {} -D && echo 'Started scamper on port 5001' && sleep 1".format(SCAMPER_PORT, SCAMPER_PPS)
CMD_LAUNCH_SC_PINGER = "sudo sc_pinger -a /home/ubuntu/{} -o {}/{} -p {} >{}/{} ; tail -1 {}/{}".format(IP_ADDRESS_LIST_FILENAME, GEOPING_RESULTS_DIR, RESULT_FILE_NAME, SCAMPER_PORT, GEOPING_RESULTS_DIR, SC_PINGER_LOG_FILEAME, GEOPING_RESULTS_DIR,SC_PINGER_LOG_FILEAME)
CMD_LAUNCH_SC_PINGER_TCP = "sudo sc_pinger -a /home/ubuntu/{} -o {}/{} -p {} -m 'tcp-syn-sport -d 80' >{}/{} ; tail -1 {}/{}".format(IP_ADDRESS_LIST_FILENAME, GEOPING_RESULTS_DIR, RESULT_FILE_NAME, SCAMPER_PORT, GEOPING_RESULTS_DIR, SC_PINGER_LOG_FILEAME, GEOPING_RESULTS_DIR,SC_PINGER_LOG_FILEAME)
CMD_LAUNCH_SC_ATTACH = "sudo sc_attach -c 'trace' -i /home/ubuntu/{} -o {}/{} -p {}".format(IP_ADDRESS_LIST_FILENAME, GEOPING_RESULTS_DIR, RESULT_FILE_NAME, SCAMPER_PORT)
CMD_COMPRESS_RESULT_FILE = "bzip2 -9 -f {}/{} && echo 'Compressed result file'".format(GEOPING_RESULTS_DIR,RESULT_FILE_NAME)
CMD_LAUNCH_EXPERIMENT = ""
if(args.launch == 'ping'):
    CMD_LAUNCH_EXPERIMENT = CMD_LAUNCH_SC_PINGER
elif(args.launch == "ping-tcp"):
    CMD_LAUNCH_EXPERIMENT = CMD_LAUNCH_SC_PINGER_TCP
elif(args.launch == "trace"):
    CMD_LAUNCH_EXPERIMENT = CMD_LAUNCH_SC_ATTACH

FINAL_CMD = ";".join([CMD_REMOVE_AND_CREATE_RESULTS_DIR,CMD_KILL_SCAMPER, CMD_START_SCAMPER, CMD_LAUNCH_EXPERIMENT, CMD_COMPRESS_RESULT_FILE])
result = local_client.cmd(TARGET, "cmd.run", [FINAL_CMD])
print("Results of running sc_pinger on all minions")
print(json.dumps(result, indent=4))
print()

# Receive the results back on the server
COMPRESSED_RESULT_FILENAME = RESULT_FILE_NAME + '.bz2'
COMPRESSED_RESULT_FILEPATH = GEOPING_RESULTS_DIR + '/' + COMPRESSED_RESULT_FILENAME
result = local_client.cmd(TARGET, "cp.push", [COMPRESSED_RESULT_FILEPATH, False, COMPRESSED_RESULT_FILENAME])
print("Results of pulling files from all minions")
print(json.dumps(result, indent=4))
print()

# Aggregate all results back in one directory
minions_cache_dir = '/var/cache/salt/master/minions'
aggregate_results_dir_basename = COMPRESSED_RESULT_FILENAME[:-10]
aggregate_results_dir = os.path.join('/home/ubuntu/aggregate-results', aggregate_results_dir_basename)

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
