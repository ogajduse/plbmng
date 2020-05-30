#! /usr/bin/env python3
# Author: Martin Kacmarcik
# License: MIT
# For my Diploma thesis at Faculty of Electrical Engineering -- Brno, University of Technology

import socket
import sys


def test_port_availability(hostname: str, port: int):
    """
    Test availability of a given port on host.

    :param hostname: Host name of a host.
    :type hostname: str
    :param port: Port number to check if is availibale.
    :type port: int
    :return: Return True if given port is available. Otherwise return False.\
    If an error has occurred, return its number.
    """
    try:
        server_ip = socket.gethostbyname(hostname)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((server_ip, port))
        if result == 0:
            return True
        else:
            return False
    except KeyboardInterrupt:
        print("You pressed Ctrl+C")
        sys.exit(96)
    except socket.gaierror:
        return 98
    except socket.error:
        return 97
    finally:
        if "sock" in locals():
            sock.close()
