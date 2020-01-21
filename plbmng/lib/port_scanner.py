#! /usr/bin/env python3
#Author: Martin Kacmarcik
#License: MIT
#For my Diploma thesis at Faculty of Electrical Engineering -- Brno, University of Technology

import socket
import sys

def testPortAvailability(hostname,port):
    try:
        server_ip  = socket.gethostbyname(hostname)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((server_ip, port))
        if result == 0:
            return True
        else:
            return False
        sock.close()
    except KeyboardInterrupt:
        print("You pressed Ctrl+C")
        sys.exit(96)
    except socket.gaierror:
        return 98
    except socket.error:
        return 97
