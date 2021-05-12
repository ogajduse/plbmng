import datetime
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
import uuid
import webbrowser
from itertools import groupby
from multiprocessing import Lock
from multiprocessing import Pool
from multiprocessing import Value
from pathlib import Path
from platform import system
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

import folium
from dialog import Dialog
from gevent import joinall
from pssh.clients.native.parallel import ParallelSSHClient

import plbmng.lib.planetlab_list_creator
from plbmng import executor
from plbmng.lib import full_map
from plbmng.lib import port_scanner
from plbmng.lib import ssh as sshlib
from plbmng.utils.config import get_db_path
from plbmng.utils.config import get_install_dir
from plbmng.utils.config import get_map_path
from plbmng.utils.config import get_remote_jobs_path
from plbmng.utils.config import settings
from plbmng.utils.logger import logger


# global variables
base = None
increment = None
lock = None

# Constant definition
OPTION_IP = "ip"
OPTION_DNS = "dns"
OPTION_CONTINENT = "continent"
OPTION_COUNTRY = "country"
OPTION_REGION = "region"
OPTION_CITY = "city"
OPTION_URL = "url"
OPTION_NAME = "full name"
OPTION_LAT = "latitude"
OPTION_LON = "longitude"
OPTION_GCC = "gcc"
OPTION_PYTHON = "python"
OPTION_KERNEL = "kernel"
OPTION_MEM = "memory"

DIALOG = None
SOURCE_PATH = None
DESTINATION_PATH = None


class NeedToFillPasswdFirstInfo(Exception):
    """Raise when password is not filled."""


def get_custom_servers(start_id: str) -> list:
    """
    Read user_servers.node file in database directory a return all servers from it as list.

    :param start_id: Starting id as string.
    :return: Return all servers from user_servers.node.
    """
    user_nodes = []
    with open(get_db_path("user_nodes")) as tsv:
        lines = tsv.read().split("\n")
    for line in lines:
        if not line:
            continue
        if line[0].startswith("#"):
            continue
        columns = line.split()
        columns.insert(0, start_id)
        if len(columns) < 11:
            for _column in range(11 - len(columns)):
                columns.append("unknown")
        try:
            user_nodes.append(columns)
            start_id += 1
        except ValueError:
            pass
    return user_nodes


def run_command(cmd: str) -> Tuple[int, str]:
    """
    Execute given cmd param as shell command.

    :param cmd: shell command as string.
    :return: Return exit code and standard outpur of given cmd.
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
    try:
        stdout, stderr = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.returncode, "unknown"
    stdout = stdout.decode("ascii", "ignore")
    stdout = stdout.rstrip("\n")
    return_code = process.returncode
    return return_code, stdout


def schedule_remote_command(cmd: str, date: datetime.datetime, hosts: List[str], db) -> None:
    """
    Schedule command (``cmd``) to run the specified ``hosts`` at the specified ``date``.

    An unique ``job_id`` is created for the pair host:command.
    There should be no more than one job with the same ID.

    :param cmd: command to be run on the remote host
    :param date: :py:class:`datetime.datetime` object representing the time in which the ``cmd`` will be executed.
    :param hosts: List of plbmng hosts on which the ``cmd`` should be run.
    :param db: plbmng database to write the job to.
    :type db: PlbmngDb
    """
    ssh_key = settings.remote_execution.ssh_key
    user = settings.planetlab.slice  # executor_dst_path = "~/.plbmng/executor.py"
    executor_dst_path = "/tmp/executor.py"
    # TODO: verify that paths are instances of Path()
    executor_path = executor.__file__
    for host in hosts:
        sshlib.upload_file(executor_path, executor_dst_path, key_filename=ssh_key, hostname=host, username=user)
        job_uuid = str(uuid.uuid4())
        executor_cmd = (
            f"python3 {executor_dst_path} --run-at {int(date.timestamp())} --run-cmd '{cmd}' --job-id {job_uuid}"
        )
        db.add_job(
            job_uuid,
            host,
            cmd,
            date.timestamp(),
            executor.PlbmngJobState["scheduled"].value,
            executor.PlbmngJobResult["pending"].value,
        )
        sshlib.command(executor_cmd, hostname=host, username=user, key_filename=ssh_key, background=True)


def get_non_stopped_jobs(db) -> List[executor.PlbmngJob]:
    """
    Get all non-stopped jobs from the plbmng database.

    :param db: plbmng database to be looked-up
    :type db: PlbmngDb
    :return: list of plbmng jobs that are not in *stopped* :py:class:`plbmng.executor.PlbmngJobState`
    """
    return db.get_non_stopped_jobs()


def get_stopped_jobs(db) -> List[executor.PlbmngJob]:
    """
    Get all stopped jobs from the plbmng database.

    :param db: plbmng database to be looked-up
    :type db: PlbmngDb
    :return: list of plbmng jobs that are in *stopped* :py:class:`plbmng.executor.PlbmngJobState`
    """
    return db.get_stopped_jobs()


def get_all_jobs(db) -> List[executor.PlbmngJob]:
    """
    Get all jobs from the plbmng database.

    :param db: plbmng database to be looked-up
    :type db: PlbmngDb
    :return: list of all plbmng jobs
    """
    return db.get_all_jobs()


def get_server_params(ip_or_hostname: str, ssh: bool = False) -> list:
    """Return versions of prepared commands as a list.

    :param ip_or_hostname: IP address of hostname of the target
    :param ssh: use ssh, defaults to :py:obj:`False`
    :return: List of requested info as string
    """
    commands = [
        "gcc -dumpversion",
        "python3 --version",
        "uname -r",
        "grep MemTotal /proc/meminfo | awk '{print $2 / 1024}'",
    ]
    if not ssh:
        # return list of unknown string depending on number of commands
        return ["unknown" for x in range(len(commands))]
    cmd = (
        "ssh -o PasswordAuthentication=no -o UserKnownHostsFile=/dev/null "
        "-o StrictHostKeyChecking=no -o LogLevel=QUIET -o ConnectTimeout=10 "
        "-i %s %s@%s " % (settings.remote_execution.ssh_key, settings.planetlab.slice, ip_or_hostname)
    )
    output = []
    for command in commands:
        try:
            ret, stdout = run_command(cmd + command)
            if ret != 0:
                output.append("unknown")
                continue
            if stdout:
                output.append(stdout)
                continue
            else:
                output.append("unknown")
        except Exception as e:
            logger.error("An error occured: {}", e)
            return ["unknown" for x in range(len(commands))]
    return output


def get_all_nodes() -> None:
    """
    Get all nodes from plbmng using planetlab_list_creator script.

    Create file default.node in plbmng database directory

    :raises NeedToFillPasswdFirstInfo: if ``username`` or ``password`` are not specified in the plbmng settings
    """
    user = settings.planetlab.username
    passwd = settings.planetlab.password
    if user != "" and passwd != "":
        os.system(
            f"pushd {get_install_dir()}; {sys.executable} {plbmng.lib.planetlab_list_creator.__file__} "
            f"-u '{user}' -p '{passwd}' -o {get_db_path('default_node')}; popd"
        )
        # TODO: show output in case of fail
    else:
        raise NeedToFillPasswdFirstInfo


def search_by_regex(nodes: list, option: int, regex: str) -> list:
    """
    Return all :param regex matched values from :param nodes at :param option index.

    :param nodes: list of nodes.
    :param option: Index in the nodes list(check constants at the start of this file).
    :param regex: Pattern to be found.
    :return: Return list of matched values as list.
    """
    answers = []
    for item in nodes:
        if re.search(regex, item[option]):
            answers.append(item[option])
    return answers


def search_by_sware_hware(nodes: list, option: int) -> dict:
    """
    Search by software/hardware.

    Return all unique entries in ``nodes`` list at ``option`` index as
    keys and all hostnameswhich contains the entry in list as value.

    :param nodes: list of nodes.
    :param option: Index in the nodes list(check constants at the start of this file).
    :return: Return dictionary of unique entries as keys and all host names in list as value.
    """
    filter_nodes = {}
    for item in nodes:
        if item[option] not in filter_nodes.keys():
            filter_nodes[item[option]] = [item["dns"]]
        else:
            filter_nodes[item[option]].append(item["dns"])
    return filter_nodes


def search_by_location(nodes: list) -> Tuple[dict, dict]:
    """
    Return two dictionaries created from :param nodes list based on their continent, country and host name.

    First dictionary contains continents(eg. EU, AS) as key and all the countries in the list(eg. ["CZ, SK"])
    Second dictionary contains country as key(eg. "CZ") and values are all the server based in the country in list.
    {"EU": ["CZ", "SK"...]}, {"cz": ["aaaa.cz", "bbbbb.cz"]}

    :param nodes: List of all available nodes.
    :return: tuple with continents and countries
    """
    continents_dict = {}
    countries = {}

    for item in nodes:
        if item[OPTION_CONTINENT] in continents_dict.keys():
            continents_dict[item[OPTION_CONTINENT]].append(item[OPTION_COUNTRY])
        else:
            continents_dict[item[OPTION_CONTINENT]] = [item[OPTION_COUNTRY]]
        if item[OPTION_COUNTRY] in countries.keys():
            countries[item[OPTION_COUNTRY]].append(item[OPTION_DNS])
        else:
            countries[item[OPTION_COUNTRY]] = [item[OPTION_DNS]]
    return continents_dict, countries


def connect(mode: int, node: list) -> None:
    """
    Connect to a node using ssh or Midnight Commander.

    :param mode: If mode is equals to 1, ssh is used. If mode is equals to 2, MC is used to connect to the node.
        If mode is different from 1 or 2, return None.
    :param node: List which contains all information from planetlab
        network about the node(must follow template from default.node).
    :raises ConnectionError: If SSH command fails.
    :raises ConnectionError: If MC fails.
    """
    clear()
    key = settings.remote_execution.ssh_key
    user = settings.planetlab.slice
    if mode == 1:
        command = 'ssh -o "StrictHostKeyChecking = no" -o "UserKnownHostsFile=/dev/null"'
        command += f" -i {key} {user}@{node[OPTION_IP]}"
        return_value = os.system(command)
        if return_value != 0:
            raise ConnectionError(f"SSH failed with error code {return_value}")
    elif mode == 2:
        os.system("ssh-add " + key)
        return_value = os.system(f"mc sh://{user}@{node[OPTION_IP]}:/home")
        if return_value != 0:
            raise ConnectionError(f"MC failed with error code {return_value}")


def show_on_map(node: list, node_info: dict = None) -> None:
    """
    Generate and open in default web browser html page with map of the world and show node on the map.

    :param node: List which contains all information from planetlab
        network about the node(must follow template from default.node).
    :param node_info: Info about node as string.
    """
    if not node_info:
        node_info = {"text": ""}
    _stderr = os.dup(2)
    os.close(2)
    _stdout = os.dup(1)
    os.close(1)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 2)
    os.dup2(fd, 1)

    latitude = float(node[OPTION_LAT])
    longitude = float(node[OPTION_LON])
    popup = folium.Popup(node_info["text"].strip().replace("\n", "<br>"), max_width=1000)
    node_map = folium.Map(location=[latitude, longitude], zoom_start=2, min_zoom=2)
    if node_info["text"] == "":
        folium.Marker([latitude, longitude], popup=popup).add_to(node_map)
    else:
        folium.Marker([latitude, longitude], popup).add_to(node_map)
    node_map.save("/tmp/map_plbmng.html")
    try:
        webbrowser.get().open("file://" + os.path.realpath("/tmp/map_plbmng.html"))
    finally:
        os.close(fd)
        os.dup2(_stderr, 2)
        os.dup2(_stdout, 1)


def plot_servers_on_map(nodes: list) -> None:
    """
    Plot every node in nodes on map.

    :param nodes: List of Planetlab nodes.
    """
    _stderr = os.dup(2)
    os.close(2)
    _stdout = os.dup(1)
    os.close(1)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 2)
    os.dup2(fd, 1)

    # update base_data.txt file based on latest database with nodes
    full_map.plot_server_on_map(nodes)
    try:
        webbrowser.get().open(f"file://{get_map_path('map_file')}")
    finally:
        os.close(fd)
        os.dup2(_stderr, 2)
        os.dup2(_stdout, 1)


def get_server_info(server_id: int, option: int, nodes: list) -> Tuple[dict, list]:
    """
    Retrieve all available info about server from ``node`` based on ``server_id``.

    Option should be index on which is server id present in node list.

    :param server_id: ID of the server.
    :param option: Index program should look for server_id in node.
    :param nodes: List of all nodes.
    :return: Return dictionary with info about node and the node found in node based on server id.
    """
    if option == 0:
        option = OPTION_DNS
    if isinstance(server_id, str):
        # in nodes find the chosen_one node
        chosen_one = ""
        for item in nodes:
            if re.search(server_id, item[option]):
                chosen_one = item
                break
        if chosen_one == "":
            logger.error("Internal error, please file a bug report via PyPi")
            exit(99)
        # get information about servers
        ip_or_hostname = chosen_one[OPTION_DNS] if chosen_one[OPTION_DNS] != "unknown" else chosen_one[OPTION_IP]
        info_about_node_dic = {}
        region, city, url, fullname, lat, lon = get_info_from_node(chosen_one)
        info_about_node_dic["region"] = region
        info_about_node_dic["city"] = city
        info_about_node_dic["url"] = url
        info_about_node_dic["fullname"] = fullname
        info_about_node_dic["lat"] = lat
        info_about_node_dic["lon"] = lon
        info_about_node_dic["icmp"] = test_ping(ip_or_hostname)
        info_about_node_dic["sshAvailable"] = test_ssh(ip_or_hostname)
        programs = get_server_params(ip_or_hostname, info_about_node_dic["sshAvailable"])
        info_about_node_dic[
            "text"
        ] = """
            NODE: %s
            IP: %s
            CONTINENT: %s, COUNTRY: %s, REGION: %s, CITY: %s
            URL: %s
            FULL NAME: %s
            LATITUDE: %s, LONGITUDE: %s
            CURRENT ICMP RESPOND: %s
            CURRENT SSH AVAILABILITY: %r
            GCC version: %s Python: %s Kernel version: %s
            """ % (
            chosen_one[OPTION_DNS],
            chosen_one[OPTION_IP],
            chosen_one[OPTION_CONTINENT],
            chosen_one[OPTION_COUNTRY],
            info_about_node_dic["region"],
            info_about_node_dic["city"],
            info_about_node_dic["url"],
            info_about_node_dic["fullname"],
            info_about_node_dic["lat"],
            info_about_node_dic["lon"],
            info_about_node_dic["icmp"],
            info_about_node_dic["sshAvailable"],
            programs[0],
            programs[1],
            programs[2],
        )
        if info_about_node_dic["sshAvailable"] is True or info_about_node_dic["sshAvailable"] is False:
            # update last server access database
            update_last_server_access(info_about_node_dic, chosen_one)
            return info_about_node_dic, chosen_one
        else:
            return {}, []


def get_info_from_node(node: list) -> Tuple[str, str, str, str, str, str]:
    """
    Return basic information from node an return it as tuple.

    :param node: List which contains all information from planetlab
        network about the node(must follow template from default.node).
    :return: Return region, city, url, full name, latitude and longitude from the node as tuple.
    """
    region = node["region"]
    city = node["city"]
    url = node["url"]
    fullname = node["full name"]
    lat = node["latitude"]
    lon = node["longitude"]
    return region, city, url, fullname, lat, lon


def clear() -> None:
    """Clear shell."""
    os.system("clear")


def test_ping(target: str, return_bool: bool = False) -> Union[str, bool]:
    """
    Try to ping :param target host and return boolean value or message\
    based on ping command return code from ping tool.

    :param target: Host name or IP address.
    :param return_bool: If set to  :py:obj:`False` return message instead of boolean.
    :return: Return message or bool value with ping result.
    """
    if system().lower() == "windows":
        ping_param = "-n"
    else:
        ping_param = "-c"
    # for Linux ping parameter takes seconds while MAC OS ping takes milliseconds
    if system().lower() == "linux":
        ping_packet_wait_time = 1
    else:
        ping_packet_wait_time = 800
    command = ["ping", ping_param, "1", target, "-W", str(ping_packet_wait_time)]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # prepare the regular expression to get time
    if system().lower() == "windows":
        avg = re.compile("Average = ([0-9]+)ms")
    else:
        avg = re.compile("min/avg/max/[a-z]+ = [0-9.]+/([0-9.]+)/[0-9.]+/[0-9.]+")
    avg_str = avg.findall(str(p.communicate()[0]))
    if p.returncode != 0:
        if not return_bool:
            return "Not reachable via ICMP"
        return False
    else:
        p.kill()
        if not return_bool:
            return avg_str[0] + " ms"
        return True


def test_ssh(target: str) -> Union[bool, int]:
    """
    Scan port 22 of the given :param target.

    :param target: Host name or IP address.
    :return: Result of the port scanning.
    """
    result = port_scanner.test_port_availability(target, 22)
    if isinstance(result, bool):
        return result
    elif result == 98:
        return result
    elif result == 97:
        return result


def verify_api_credentials_exist() -> bool:
    """
    Verify that user credentials are set in the plbmng conf file.

    :return: Return  :py:obj:`False` if USERNAME or PASSWORD is not set. If both are set, return :py:obj:`True`.
    """
    try:
        assert settings.planetlab.username and settings.planetlab.username != ""
        assert settings.planetlab.password and settings.planetlab.password != ""
    except AssertionError:
        return False
    return True


def verify_ssh_credentials_exist() -> bool:
    """
    Verify that SLICE NAME(user acc on remote host) and path to SSH key are set in the plbmng conf file.

    :return: Return :py:obj:`False` if SLICE_NAME or SSH_KEY is not set. If both are set, return :py:obj:`True`.
    """
    try:
        assert settings.planetlab.slice and settings.planetlab.slice != ""
        assert settings.remote_execution.ssh_key and settings.remote_execution.ssh_key != ""
    except AssertionError:
        return False
    return True


def update_last_server_access(info_about_node_dic: dict, chosen_node: list) -> None:
    """
    Update file which contains all the information about last accessed node by user.

    :param info_about_node_dic: Dictionary which contains all the info about node.
    :param chosen_node: List which contains all information from planetlab
        network about the node(must follow template from default.node).
    """
    last_server_file = get_db_path("last_server", failsafe=True)
    with open(last_server_file, "w") as last_server_file:
        last_server_file.write(repr((info_about_node_dic, chosen_node)))


def get_last_server_access() -> Tuple[dict, list]:
    """
    Return dictionary and list in tuple with all the available information about the last accessed node.

    :return: info_about_node_dic and chosen_node.
    :raises FileNotFoundError: if the last_server file does not exist
    """
    last_server_file = get_db_path("last_server")
    if not os.path.exists(last_server_file):
        raise FileNotFoundError
    with open(last_server_file, "r") as last_server_file:
        info_about_node_dic, chosen_node = eval(last_server_file.read().strip("\n"))
    return info_about_node_dic, chosen_node


def server_choices(returned_choice: int, chosen_node: list, info_about_node_dic: dict = None) -> None:
    """
    Prepare choices for user to connect or generate HTML page with map.

    Based on the :param returned_choice, execute function with given parameters.

    :param returned_choice: Number 1-3 specified by user in DIALOG window.
    :param chosen_node: List which contains all information from planetlab
        network about the node(must follow template from default.node).
    :param info_about_node_dic: Dictionary which contains all the info about node.
    :return: None
    """
    if returned_choice is None:
        return None
    elif not returned_choice:
        return None
    elif int(returned_choice) == 1:
        connect(int(returned_choice), chosen_node)
    elif int(returned_choice) == 2:
        connect(int(returned_choice), chosen_node)
    elif int(returned_choice) == 3:
        show_on_map(chosen_node, info_about_node_dic)


def update_availability_database_parent(dialog: Dialog, nodes: list = None) -> None:
    """
    Initialize parallel updating of the plbmng database.

    :param dialog: Instance of a dialog engine.
    :param nodes: List of nodes to update the database.
    """
    global DIALOG
    increment = Value("f", 0)
    increment.value = float(100 / len(nodes))
    base = Value("f", 0)
    lock = Lock()
    DIALOG = dialog
    dialog.gauge_start()
    try:
        pool = Pool(initializer=multi_processing_init, initargs=(lock, base, increment))
    except sqlite3.OperationalError:
        dialog.msgbox("Could not update database")
    pool.map(update_availability_database, nodes)
    pool.close()
    pool.join()
    dialog.gauge_update(100, "Completed")
    dialog.gauge_stop()
    dialog.msgbox("Availability database has been successfully updated")


def multi_processing_init(i_lock: Lock, i_base: Value, i_increment: Value) -> None:
    """
    Initialize Pool.

    :param i_lock: Lock to synchronize processes.
    :param i_base: Progress of updating the database. Value is used in DIALOG gauge.
    :param i_increment: Incremental value in % added to :param base when process is done.
    """
    global lock
    lock = i_lock
    global base
    base = i_base
    global increment
    increment = i_increment


def update_availability_database(node: list) -> None:
    """
    Update database with given information from :param node.

    :param node: List which contains all information from planetlab
        network about the node (must follow template from default.node).
    """
    # inint block
    global DIALOG  # ,PLBMNG_DATABASE
    db = sqlite3.connect(get_db_path("plbmng_database"))
    cursor = db.cursor()
    # action block
    ip_or_hostname = node["dns"] if node["dns"] else node["ip"]
    hash_object = hashlib.md5(ip_or_hostname.encode())
    ssh_result = "T" if test_ssh(ip_or_hostname) is True else "F"
    ping_result = "T" if test_ping(ip_or_hostname, True) is True else "F"
    ssh = True if ssh_result == "T" else False
    programs = get_server_params(ip_or_hostname, ssh)

    # find if object exists in the database
    sql = """SELECT nkey from availability
             WHERE shash = "{hash}";""".format(
        hash=str(hash_object.hexdigest())
    )
    cursor.execute(sql)
    if cursor.fetchone() is None:
        sql = """INSERT INTO availability(shash, shostname, bssh, bping)
                 VALUES ("{hash}", "{ip_hstnm}", "{ssh_res}", "{ping_res}");""".format(
            hash=hash_object.hexdigest(), ip_hstnm=ip_or_hostname, ssh_res=ssh_result, ping_res=ping_result
        )
    else:
        sql = """UPDATE availability
                 SET bssh="{bssh}", bping="{bping}"
                 WHERE shash="{shash}";""".format(
            bssh=ssh_result, bping=ping_result, shash=hash_object.hexdigest()
        )
    cursor.execute(sql)

    sql = """SELECT nkey
             FROM programs
             WHERE shash="{shash}";""".format(
        shash=str(hash_object.hexdigest())
    )
    cursor.execute(sql)

    if cursor.fetchone() is None:
        sql = """INSERT INTO programs(shash, shostname, sgcc, spython, skernel, smem)
                 VALUES ("{shash}", "{shostname}", "{sgcc}", "{spython}", "{skernel}", "{smem}");""".format(
            shash=hash_object.hexdigest(),
            shostname=ip_or_hostname,
            sgcc=programs[0],
            spython=programs[1],
            skernel=programs[2],
            smem=programs[3],
        )
    else:
        sql = """UPDATE programs
                 SET sgcc="{sgcc}", spython="{spython}", skernel="{skernel}", smem="{smem}")
                 WHERE shash="{shash}";""".format(
            shash=hash_object.hexdigest(),
            sgcc=programs[0],
            spython=programs[1],
            skernel=programs[2],
            smem=programs[3],
        )
    cursor.execute(sql)
    # clean up

    lock.acquire()
    base.value = base.value + increment.value
    DIALOG.gauge_update(int(base.value))
    lock.release()
    db.commit()
    db.close()


def secure_copy(host: str) -> bool:
    """
    Copy ``SOURCE_PATH`` to the ``DESTINATION_PATH`` to ``host``.

    **Global parameters must be set first!**

    :param host: IP address or host name.
    :return: Return :py:obj:`True` if command has failed. Otherwise return :py:obj:`False`.
    """
    global SOURCE_PATH, DESTINATION_PATH
    ssh_key = settings.remote_execution.ssh_key
    user = settings.planetlab.slice
    cmd = (
        "scp -r -o PasswordAuthentication=no -o UserKnownHostsFile=/dev/null "
        "-o StrictHostKeyChecking=no -o LogLevel=QUIET "
        "-i %s %s %s@%s:%s" % (ssh_key, SOURCE_PATH, user, host, DESTINATION_PATH)
    )
    ret, stdout = run_command(cmd)
    lock.acquire()
    base.value = base.value + increment.value
    DIALOG.gauge_update(int(base.value))
    lock.release()
    if ret != 0:
        return True
    return False


def jobs_downloaded_artefacts(jobs: List[executor.PlbmngJob]) -> List[executor.PlbmngJob]:
    """
    Return all jobs that have artefacts downloaded.

    :param jobs: list of plbmng jobs to be looked up
    :return: list of plbmng jobs that have artefacts downloaded
    """
    return [job for job in jobs if Path(f"{get_remote_jobs_path()}/{job.hostname}/{job.job_id}").exists()]


def parallel_copy(dialog, source_path: str, hosts: list, destination_path: str) -> bool:
    """
    Perform parallel copy of the local file to the remote host.

    :param dialog: Instance of dialog engine.
    :param source_path: File or directory to be copied.
    :param hosts: List of hosts(ip addressed or host names).
    :param destination_path: Path on the target where should be file or directory copied to.
    :return: True if source path has been copied successfully to all hosts.
    """
    global DIALOG, SOURCE_PATH, DESTINATION_PATH
    DIALOG = dialog
    SOURCE_PATH = source_path
    DESTINATION_PATH = destination_path
    increment = Value("f", 0)
    increment.value = float(100 / len(hosts))
    base = Value("f", 0)
    lock = Lock()
    DIALOG = dialog
    dialog.gauge_start()
    pool = Pool(initializer=multi_processing_init, initargs=(lock, base, increment))
    ret = pool.map(secure_copy, hosts)
    pool.close()
    pool.join()
    dialog.gauge_update(100, "Completed")
    dialog.gauge_stop()
    # if ret is empty list, return False
    if not ret:
        return False
    # any -> If at least one scp command failed(secure_copy returned True), return False
    return not any(ret)


def copy_files(dialog: Dialog, source_path: str, hosts: list, destination_path: str) -> bool:
    """
    Perform copy of the file specified by ``source_path`` to the ``destination_path`` at the specified ``hosts``.

    :param dialog: Instance of dialog engine.
    :param source_path: Path of the file to copy.
    :param hosts: List of hosts on which the file should be copied.
    :param destination_path: Path to the destination file that will be copied.
    :return: :py:obj:`True` if all copy operations were performed successfully, :py:obj:`False` otherwise.
    """
    ssh_key = settings.remote_execution.ssh_key
    user = settings.planetlab.slice
    dialog.gauge_start()
    # TODO: Parallelize this method and work properly with gauges.
    # TODO: Add possibility to copy directories recursively.
    for host in hosts:
        try:
            sshlib.upload_file(source_path, destination_path, key_filename=ssh_key, hostname=host, username=user)
        except OSError:
            return False
    dialog.gauge_update(100, "Completed")
    return True


def run_remote_command(dialog: Dialog, command: str, hosts: list) -> bool:
    """
    Run ``command`` on the specified ``hosts``.

    :param dialog: Instance of dialog.
    :param command: Command to be run on the specified ``hosts``.
    :param hosts: List of hosts on which the ``command`` should be executed.
    :return: :py:obj:`True` if all commands ended successfully, :py:obj:`False` otherwise.
    """
    ssh_key = settings.remote_execution.ssh_key
    user = settings.planetlab.slice
    dialog.gauge_start()
    # TODO: Parallelize this method and work properly with gauges.
    try:
        for host in hosts:
            sshlib.command(command, hostname=host, username=user, key_filename=ssh_key)
        dialog.gauge_update(100, "Completed")
    except Exception:
        return False
    return True


def get_remote_jobs(host: str) -> List[executor.PlbmngJob]:
    """
    Return all jobs found in the *jobs.json* of the given ``host``.

    :param host: The ``host`` whose entities are to be returned.
    :return: List of jobs for the given ``host``.
    """
    with executor.PlbmngJobsFile(f"{get_remote_jobs_path()}/jobs.json_{host}") as jobs:
        return jobs.jobs


def delete_jobs(db, jobs: List[executor.PlbmngJob]) -> None:
    """
    Delete all ``jobs``.

    :param db: plbmng database to be manipulated with
    :type db: PlbmngDb
    :param jobs: list of plbmng jobs to be deleted
    """
    jobs = sorted(jobs, key=lambda job: job.hostname)
    hosts = groupby(jobs, lambda job: job.hostname)
    hosts: Dict[str, List[executor.PlbmngJob]] = {host: list(jobs) for host, jobs in hosts}

    delete_remote_host_jobs(hosts)
    for host in hosts:
        for job in hosts[host]:
            delete_job(db, job)


def delete_remote_host_jobs(hosts: Dict[str, List[executor.PlbmngJob]]) -> None:
    """
    Delete :py:class:`plbmng.executor.PlbmngJob`/s from the remote hosts.

    :param hosts: Dictionary containing hosts. For each host a list of jobs is defined.
    """
    hosts_list = list(hosts.keys())
    ssh_key = settings.remote_execution.ssh_key
    user = settings.planetlab.slice
    file_name = "jobs.json"
    separator = "_"

    # get jobs.json from the host
    client = ParallelSSHClient(hosts_list, user=user, pkey=ssh_key)
    cmds = client.copy_remote_file(
        f"/home/{user}/.plbmng/{file_name}", f"{get_remote_jobs_path()}/{file_name}", suffix_separator=separator
    )
    joinall(cmds, raise_error=True)

    # remove jobs from jobs.json
    for host in hosts:
        try:
            with executor.PlbmngJobsFile(f"{get_remote_jobs_path()}/{file_name}{separator}{host}") as jf:
                for job in hosts[host]:
                    jf.del_job(job)
        except Exception:
            pass  # ignore all exceptions raised during manipulation with jobs file

    # copy jobs.json back to the host
    copy_args = [
        {
            "local_file": f"{get_remote_jobs_path()}/{file_name}{separator}{host}",
            "remote_file": f"/home/{user}/.plbmng/{file_name}",
        }
        for host in hosts_list
    ]
    cmds = client.copy_file("%(local_file)s", "%(remote_file)s", copy_args=copy_args)
    joinall(cmds, raise_error=True)


def delete_job(db, job: plbmng.executor.PlbmngJob) -> None:
    """
    Delete :py:class:`plbmng.executor.PlbmngJob`.

    Job is deleted from the following places:
        - local plbmng database
        - remote host job from *jobs.json*
        - artefacts on remote host
        - local artefacts

    :param db: plbmng database to be manipulated with
    :type db: PlbmngDb
    :param job: job to be deleted
    """

    def rm_tree(pth):
        pth = Path(pth)
        for child in pth.glob("*"):
            if child.is_file():
                child.unlink()
            else:
                rm_tree(child)
        pth.rmdir()

    # delete from database
    db.delete_job(job)
    # delete job artefacts
    files_to_delete = [f"{get_remote_jobs_path()}/jobs.json_{job.hostname}", f"{get_remote_jobs_path()}/{job.hostname}"]
    for file in files_to_delete:
        try:
            if Path(file).is_file():
                Path(file).unlink()
            else:
                rm_tree(file)
        except FileNotFoundError:
            pass
