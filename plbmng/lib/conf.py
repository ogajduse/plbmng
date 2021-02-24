import os
import re


PLBMNG_CONF = "/conf/plbmng.conf"


def get_path() -> str:
    """
    Return absolute path to the source directory of plbmng.

    :return: absolute path to the source directory of plbmng as str.
    :rtype: str
    """
    path = os.path.dirname(os.path.realpath(__file__)).rstrip("/lib")
    os.chdir(path)
    return path


def get_ssh_key() -> str:
    """
    Return path to the ssh key from plbmng conf file as string.

    return: Path to the ssh key as string.
    :rtype: str
    """
    ssh_path = ""
    with open(get_path() + PLBMNG_CONF, "r") as config:
        for line in config:
            if re.search("SSH_KEY", line):
                ssh_path = (re.sub("SSH_KEY=", "", line)).rstrip()
    return ssh_path


def get_ssh_user() -> str:
    """
    Return slice name(remote user) from plbmng conf file as string.

    :return: Slice name(remote user) as string.
    :rtype: str
    """
    user = ""
    with open(get_path() + PLBMNG_CONF, "r") as config:
        for line in config:
            if re.search("SLICE=", line):
                user = (re.sub("SLICE=", "", line)).rstrip()
    return user


def get_user() -> str:
    """
    Return user name from plbmng conf file as string.

    :return: User name as string.
    :rtype: str
    """
    user = ""
    with open(get_path() + PLBMNG_CONF, "r") as config:
        for line in config:
            if re.search("USERNAME=", line):
                user = (re.sub("USERNAME=", "", line)).rstrip()
    return user


def get_passwd() -> str:
    """
    Return password from plbmng conf file as string.

    :return: Password as string.
    :rtype: str
    """
    passwd = ""
    with open(get_path() + PLBMNG_CONF, "r") as config:
        for line in config:
            if re.search("PASSWORD=", line):
                passwd = (re.sub("PASSWORD=", "", line)).rstrip()
    return passwd
