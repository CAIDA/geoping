import json
import subprocess
import sys
import boto3
from datetime import datetime

def load_ip_hostname_map(trace_file):
    with open(trace_file, 'r') as f:
        servers = json.load(f)
    ip_hostname_map = {}
    for server in servers:
        if 'ipv4' in server:
            ip_hostname_map[server['ipv4']] = server['host']
        if 'ipv6' in server:
            ip_hostname_map[server['ipv6']] = server['host']
    return ip_hostname_map

def parse_warts_to_json(warts_file):
    # Run sc_warts2json command and capture output
    result = subprocess.run(['sc_warts2json', warts_file], stdout=subprocess.PIPE, text=True)
    json_objects = result.stdout.splitlines()
    parsed_data = [json.loads(obj) for obj in json_objects]
    return parsed_data

def get_latency(warts_file, ip_hostname_map):
    data = parse_warts_to_json(warts_file)

    rtt_values = []

    for trace in data:
        if trace["type"] == "cycle-start":
            region = trace["hostname"]
            provider = region.split("-")[0]
        if trace["type"] == "trace" and trace["stop_reason"] == "COMPLETED":
            dst = trace["dst"]
            last_hop = trace["hops"][-1]
            if dst == last_hop["addr"]:
                hostname = ip_hostname_map.get(dst, dst)
                rtt_values.append({
                    'Provider': provider,
                    'Region': region,
                    'Hostname' : hostname,
                    'Destination_address': dst,
                    'rtt': last_hop["rtt"],
                    'Timestamp': int(datetime.now().timestamp())  # Add current timestamp
                })

    return rtt_values

def upload_to_timestream(records, database_name, table_name):
    with open('config.json', 'r') as config:
        credentials = json.load(config)

    timestream = boto3.client('timestream-write',
        aws_access_key_id=credentials['access_key'],
        aws_secret_access_key=credentials['secret_key'],
        region_name="us-east-2")
    
    timestream_records = []
    for record in records:
        timestream_record = {
            'Dimensions': [
                {'Name': 'Provider', 'Value': record['Provider']},
                {'Name': 'Region', 'Value': record['Region']},
                {'Name': 'Hostname', 'Value': record['Hostname']},
                {'Name': 'Destination_address', 'Value': record['Destination_address']}
            ],
            'MeasureName': 'rtt',
            'MeasureValue': str(record['rtt']),
            'MeasureValueType': 'DOUBLE',
            'Time': str(record['Timestamp']),
            'TimeUnit': 'SECONDS'
        }
        timestream_records.append(timestream_record)

    batch_size = 100
    for i in range(0, len(timestream_records), batch_size):
        batch = timestream_records[i:i + batch_size]
        try:
            response = timestream.write_records(
                DatabaseName=database_name,
                TableName=table_name,
                Records=batch
            )
            print(f'WriteRecords Status for batch {i // batch_size + 1}:', response['ResponseMetadata']['HTTPStatusCode'])
        except Exception as e:
            print('Error:', e)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <warts_file> <trace_file>")
        sys.exit(1)

    warts_file = sys.argv[1]
    trace_file = sys.argv[2]
    ip_hostname_map = load_ip_hostname_map(trace_file)
    records = get_latency(warts_file, ip_hostname_map)
    upload_to_timestream(records, "GeopingTest", "mytable")
