import json
import socket

with open('trace.json', 'r') as f:
    servers = json.load(f)

with open('ip.txt', 'w') as ip:
    for server in servers:
        hostname = server['host'].split(':')[0]
        try:
            # Get address info for the hostname
            addrinfo = socket.getaddrinfo(hostname, None)
            addresses = set()

            # Collect IPv4 and IPv6 addresses
            for info in addrinfo:
                addresses.add(info[4][0])

            # Write addresses to the file
            for address in addresses:
                ip.write(address + '\n')
        except socket.gaierror:
            print(f"Could not resolve {hostname}")
