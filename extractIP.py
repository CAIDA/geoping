import json
import socket

with open('trace.json', 'r') as f:
    servers = json.load(f)

with open('ip.txt', 'w') as ip, open('trace2.json', 'w') as trace2_file:
    alldata = []
    for server in servers:
        hostname = server['host'].split(':')[0]
        addresses = set()
        try:
            # Get address info for the hostname
            addrinfo = socket.getaddrinfo(hostname, None)
            # Collect IPv4 and IPv6 addresses
            for info in addrinfo:
                addresses.add(info[4][0])
        except socket.gaierror:
            print(f"Could not resolve {hostname}")
        
        for address in addresses:
            ip.write(address + '\n')
            if '.' in address:
                server['ipv4']=address
            if ':' in address:
                server['ipv6']=address
        alldata.append(server)

    json.dump(alldata, trace2_file, indent=4)



