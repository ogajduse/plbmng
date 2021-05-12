#! /usr/bin/env python3
import socket
import sys
from typing import Union


def test_port_availability(hostname: str, port: int) -> Union[bool, int]:
    """
    Test availability of a given port on host.

    :param hostname: Host name of a host.
    :param port: Port number to check if is availibale.
    :return: Return :py:obj:`True` if given port is available. Otherwise return :py:obj:`False`.
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
        sys.exit(96)
    except socket.gaierror:
        return 98
    except socket.error:
        return 97
    finally:
        if "sock" in locals():
            sock.close()
