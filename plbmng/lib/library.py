from platform import system
from plbmng.lib import full_map
from plbmng.lib import port_scanner
from multiprocessing import Pool, Lock, Value
import subprocess
import re
import os
import webbrowser
import folium
import sqlite3
import hashlib

# global variables
base = None
increment = None
lock = None

# Constant definition
OPTION_LOCATION = 0
OPTION_IP = 1
OPTION_DNS = 2
OPTION_CONTINENT = 3
OPTION_COUNTRY = 4
OPTION_REGION = 5
OPTION_CITY = 6
OPTION_URL = 7
OPTION_NAME = 8
OPTION_LAT = 9
OPTION_LON = 10
OPTION_GCC = 11
OPTION_PYTHON = 12
OPTION_KERNEL = 13
OPTION_MEM = 14

USER_NODES = "/database/user_servers.node"
LAST_SERVER = "/database/last_server.node"
PLBMNG_DATABASE = "/database/internal.db"
PLBMNG_CONF = "/conf/plbmng.conf"
FIRST_RUN_FILE = "/database/first.boolean"
MAP_FILE = "plbmng_server_map.html"
DIALOG = None
SOURCE_PATH = None
DESTINATION_PATH = None


class NeedToFillPasswdFirstInfo(Exception):
    """Raise when password is not filled"""


class NonZeroReturnCode(Exception):
    """Raise when return code is not equal to 0"""


def get_custom_servers(start_id: str) -> list:
    """
    Read user_servers.node file in database directory a return all servers from it as list.

    :param start_id: Starting id as string.
    :type start_id: str
    :return: Return all servers from user_servers.node.
    :rtype: list
    """
    user_nodes = []
    with open(get_path() + USER_NODES) as tsv:
        lines = tsv.read().split("\n")
    for line in lines:
        if not line:
            continue
        if line[0].startswith('#'):
            continue
        columns = line.split()
        columns.insert(0, start_id)
        if len(columns) < 11:
            for column in range(11 - len(columns)):
                columns.append("unknown")
        try:
            user_nodes.append(columns)
            start_id += 1
        except ValueError:
            pass
    return user_nodes


def run_command(cmd: str) -> (int, str):
    """
    Executes given cmd param as shell command.

    :param cmd: shell command as string.
    :type cmd: str
    :return: Return exit code and standard outpur of given cmd.
    :rtype: tuple
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
    try:
        stdout, stderr = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.returncode, "unknown"
    stdout = stdout.decode('ascii', 'ignore')
    stdout = stdout.rstrip("\n")
    return_code = process.returncode
    return return_code, stdout


def get_server_params(ip_or_hostname: str, ssh=False) -> list:
    """
    Return versions of prepared commands as list.

    :param ip_or_hostname: IP address of hostname of the target
    :type ip_or_hostname: str
    :param ssh:
    :type ssh: bool
    :return: List of requested info as string
    :rtype: list
    """
    commands = ["gcc -dumpversion", "python3 --version", "uname -r",
                "grep MemTotal /proc/meminfo | awk '{print $2 / 1024}'",
                ]
    if not ssh:
        # return list of unknown string depending on number of commands
        return ["unknown" for x in range(len(commands))]
    cmd = 'ssh -o PasswordAuthentication=no -o UserKnownHostsFile=/dev/null ' \
          '-o StrictHostKeyChecking=no -o LogLevel=QUIET -o ConnectTimeout=10 ' \
          '-i %s %s@%s ' % (get_ssh_key(), get_ssh_user(), ip_or_hostname)
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
            print(e)
            return ["unknown" for x in range(len(commands))]
    return output


def get_ssh_key() -> str:
    """
    Return path to the ssh key from plbmng conf file as string.

    return: Path to the ssh key as string.
    :rtype: str
    """
    ssh_path = ""
    with open(get_path() + PLBMNG_CONF, 'r') as config:
        for line in config:
            if re.search('SSH_KEY', line):
                ssh_path = (re.sub('SSH_KEY=', '', line)).rstrip()
    return ssh_path


def get_ssh_user() -> str:
    """
    Return slice name(remote user) from plbmng conf file as string.

    :return: Slice name(remote user) as string.
    :rtype: str
    """
    user = ""
    with open(get_path() + PLBMNG_CONF, 'r') as config:
        for line in config:
            if re.search('SLICE=', line):
                user = (re.sub('SLICE=', '', line)).rstrip()
    return user


def get_user() -> str:
    """
    Return user name from plbmng conf file as string.

    :return: User name as string.
    :rtype: str
    """
    user = ""
    with open(get_path() + PLBMNG_CONF, 'r') as config:
        for line in config:
            if re.search('USERNAME=', line):
                user = (re.sub('USERNAME=', '', line)).rstrip()
    return user


def get_passwd() -> str:
    """
    Return password from plbmng conf file as string.

    :return: Password as string.
    :rtype: str
    """
    passwd = ""
    with open(get_path() + PLBMNG_CONF, 'r') as config:
        for line in config:
            if re.search('PASSWORD=', line):
                passwd = (re.sub('PASSWORD=', '', line)).rstrip()
    return passwd


def get_all_nodes():
    """
    Get all nodes from plbmng using planetlab_list_creator script.

    :raise: NeedToFillPasswdFirstInfo
    :return: Create file default.node in plbmng database directory
    """
    user = get_user()
    passwd = get_passwd()
    if user != "" and passwd != "":
        os.system(
            "myPwd=$(pwd); cd " + get_path() + "; python3 lib/planetlab_list_creator.py "
                                               "-u \"" + user + "\" -p \"" + passwd + "\" -o ./; cd $(echo $myPwd)")
    else:
        raise NeedToFillPasswdFirstInfo


def is_first_run() -> bool:
    """
    Check first.boolean file in database directory if the user is
    using plbmng for the first time. If so, rewrites the value in the file.

    :return: True if user is using plbmng for the first time.
    :rtype: bool
    """
    is_first = get_path() + FIRST_RUN_FILE
    with open(is_first, 'r') as isFirstFile:
        bool_is_first = isFirstFile.read().strip('\n')
    if bool_is_first == "True":
        with open(is_first, 'w') as is_first_file:
            is_first_file.write("False")
        return True
    else:
        return False


def search_by_regex(nodes: list, option: int, regex: str) -> list:
    """
    Return all :param regex matched values from :param nodes at :param option index.

    :param nodes: list of nodes.
    :type nodes: list
    :param option: Index in the nodes list(check constants at the start of this file).
    :type option: str
    :param regex: Pattern to be found.
    :type regex: str
    :return: Return list of matched values as list.
    """
    answers = []
    for item in nodes:
        if re.search(regex, item[option]):
            answers.append(item[option])
    return answers


def search_by_sware_hware(nodes: list, option: int) -> dict:
    """
    Return all unique entries in :param nodes list at :param option index
    as keys and all host names which contains the entry in list as value.

    :param nodes: list of nodes.
    :type nodes: list
    :param option: Index in the nodes list(check constants at the start of this file).
    :type option: int
    :return: Return dictionary of unique entries as keys and all host names in list as value.
    :rtype: dict
    """
    filter_nodes = {}
    for item in nodes:
        if item[option] not in filter_nodes.keys():
            filter_nodes[item[option]] = [item[OPTION_DNS]]
        else:
            filter_nodes[item[option]].append(item[OPTION_DNS])
    return filter_nodes


def search_by_location(nodes: list) -> (dict, dict):
    """
    Return two dictionaries created from :param nodes list based on their continent, country and host name.\
    First dictionary contains continents(eg. EU, AS) as key and all the countries in the list(eg. ["CZ, SK"])\
    Second dictionary contains country as key(eg. "CZ") and values are all the server based in the country in list.\
    {"EU": ["CZ", "SK"...]}, {"cz": ["aaaa.cz", "bbbbb.cz"]}

    :param nodes: List of all available nodes.
    :type nodes: list
    :rtype: tuple
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


def connect(mode: int, node: list):
    """
    Connect to a node using ssh or Midnight Commander.

    :param mode: If mode is equals to 1, ssh is used. If mode is equals to 2, MC is used to connect to the node.\
                 If mode is different from 1 or 2, return None.
    :type mode: int
    :param node: List which contains all information from planetlab\
    network about the node(must follow template from default.node).
    :type node: list
    :raises: ConnectionError
    """
    clear()
    key = get_ssh_key()
    user = get_ssh_user()
    if mode == 1:
        return_value = os.system(
            "ssh -o \"StrictHostKeyChecking = no\" -o \"UserKnownHostsFile=\
            /dev/null\" -i " + key + " " + user + "@" + node[OPTION_IP])
        if return_value != 0:
            raise ConnectionError("SSH failed with error code %s" % return_value)
    elif mode == 2:
        os.system('ssh-add ' + key)
        return_value = os.system("mc sh://" + user + "@" + node[OPTION_IP] + ":/home")
        if return_value != 0:
            raise ConnectionError("MC failed with error code %s" % return_value)


def show_on_map(node: list, node_info="") -> None:
    """
    Generate and open in default web browser html page with map of the world and show node on the map.

    :param node: List which contains all information from planetlab\
    network about the node(must follow template from default.node).
    :type node: list
    :param node_info: Info about node as string.
    :type node_info: str
    :rtype: None
    """
    _stderr = os.dup(2)
    os.close(2)
    _stdout = os.dup(1)
    os.close(1)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 2)
    os.dup2(fd, 1)

    latitude = float(node[OPTION_LAT])
    longitude = float(node[OPTION_LON])
    popup = folium.Popup(node_info["text"].strip().replace('\n', '<br>'), max_width=1000)
    node_map = folium.Map(location=[latitude, longitude],
                          zoom_start=2, min_zoom=2)
    if node_info == "":
        folium.Marker([latitude, longitude], popup=popup).add_to(node_map)
    else:
        folium.Marker([latitude, longitude], popup).add_to(node_map)
    node_map.save('/tmp/map_plbmng.html')
    try:
        webbrowser.get().open('file://' + os.path.realpath('/tmp/map_plbmng.html'))
    finally:
        os.close(fd)
        os.dup2(_stderr, 2)
        os.dup2(_stdout, 1)


def plot_servers_on_map(nodes: list, path: str) -> None:
    """
    Plot every node in nodes on map.

    :param nodes: List of Planetlab nodes.
    :type nodes: list
    :param path: path to the directory which contains MAP_FILE.
    :type path: str
    :rtype: None
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
        webbrowser.get().open('file://' + os.path.realpath(path + "/" + MAP_FILE))
    finally:
        os.close(fd)
        os.dup2(_stderr, 2)
        os.dup2(_stdout, 1)


def get_server_info(server_id: int, option: int, nodes: list) -> (dict, list):
    """
    Retrieve all available info about server from :param node
    based on :param server_id. Option should be index on which is server id present in node list.

    :param server_id: ID of the server.
    :type server_id: int
    :param option: Index program should look for server_id in node.
    :type option: int
    :param nodes: List of all nodes.
    :type nodes: list
    :return: Return dictionary with info about node and the node found in node based on server id.
    :rtype: tuple
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
            print("Internal error, please file a bug report via PyPi")
            exit(99)
        # get information about servers
        ip_or_hostname = chosen_one[OPTION_DNS] if chosen_one[OPTION_DNS] != "unknown" else chosen_one[OPTION_IP]
        info_about_node_dic = dict()
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
        info_about_node_dic["text"] = """
            NODE: %s
            IP: %s
            CONTINENT: %s, COUNTRY: %s, REGION: %s, CITY: %s
            URL: %s
            FULL NAME: %s
            LATITUDE: %s, LONGITUDE: %s
            CURRENT ICMP RESPOND: %s
            CURRENT SSH AVAILABILITY: %r
            GCC version: %s Python: %s Kernel version: %s
            """ % (chosen_one[OPTION_DNS],
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
                   programs[2])
        if info_about_node_dic["sshAvailable"] is True or info_about_node_dic["sshAvailable"] is False:
            # update last server access database
            update_last_server_access(info_about_node_dic, chosen_one, get_path())
            return info_about_node_dic, chosen_one
        else:
            return {}, []


def get_info_from_node(node: list) -> tuple:
    """
    Return basic information from node an return it as tuple

    :param node: List which contains all information from planetlab\
    network about the node(must follow template from default.node).
    :type node: list
    :return: Return region, city, url, full name, latitude and longitude from the node as tuple.
    :rtype: tuple
    """
    region = node[5]
    city = node[6]
    url = node[7]
    fullname = node[8]
    lat = node[9]
    lon = node[10]
    return region, city, url, fullname, lat, lon


"""
DEPRECATED FUNCTION
def remove_cron():
    os.system("crontab -l | grep -v \"plbmng crontab\" | crontab -")

    def add_to_cron(mode):
    if int(mode) == 1:
        line = "@daily plbmng crontab"
    elif int(mode) == 2:
        line = "@weekly plbmng crontab"
    elif int(mode) == 3:
        line = "@monthly plbmng crontab"
    os.system("echo \"$(crontab -l ; echo " + line + ")\" | crontab -")
"""


def get_path() -> str:
    """
    Return absolute path to the source directory of plbmng.

    :return: absolute path to the source directory of plbmng as str.
    :rtype: str
    """
    path = os.path.dirname(os.path.realpath(__file__)).rstrip("/lib")
    os.chdir(path)
    return path


def clear() -> None:
    """
    Clear shell.
    """
    os.system("clear")


def test_ping(target: str, return_bool=False):
    """
    Try to ping :param target host and return boolean value or message\
    based on ping command return code from ping tool.

    :param target: Host name or IP address.
    :type target: str
    :param return_bool: If set to False return message instead of boolean.
    :type return_bool: bool
    :return: Return message or bool value with ping result.
    """
    if system().lower() == 'windows':
        ping_param = '-n'
    else:
        ping_param = '-c'
    # for Linux ping parameter takes seconds while MAC OS ping takes milliseconds
    if system().lower() == 'linux':
        ping_packet_wait_time = 1
    else:
        ping_packet_wait_time = 800
    command = ['ping', ping_param, '1', target, '-W', str(ping_packet_wait_time)]
    p = subprocess.Popen(command, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    # prepare the regular expression to get time
    if system().lower() == 'windows':
        avg = re.compile('Average = ([0-9]+)ms')
    else:
        avg = re.compile(
            'min/avg/max/[a-z]+ = [0-9.]+/([0-9.]+)/[0-9.]+/[0-9.]+')
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


def test_ssh(target: str):
    """
    Scan port 22 of the given :param target.

    :param target: Host name or IP address.
    :type target: str
    :return: Result of the port scanning.
    """
    result = port_scanner.test_port_availability(target, 22)
    if result is True or result is False:
        return result
    elif result == 98:
        return result
    elif result == 97:
        return result


def verify_api_credentials_exist(path: str) -> bool:
    """
    Verify that user credentials are set in the plbmng conf file.

    :param path: Path to the source directory of plbmng.
    :type path: str
    :return: Return False if USERNAME or PASSWORD is not set. If both are set, return True.
    :rtype: bool
    """
    with open(path + "/conf/plbmng.conf", 'r') as config:
        for line in config:
            if re.search('USERNAME', line):
                username = re.sub('USERNAME="(.*)"', r'\1', line).rstrip()
                if not username:
                    return False
            elif re.search('PASSWORD', line):
                password = re.sub('PASSWORD="(.*)"', r'\1', line).rstrip()
                if not password:
                    return False
    return True


def verify_ssh_credentials_exist(path: str) -> bool:
    """
    Verify that SLICE NAME(user acc on remote host) and path to SSH key are set in the plbmng conf file.

    :param path: Path to the source directory of plbmng.
    :type path: str
    :return: Return False if SLICE_NAME or SSH_KEY is not set. If both are set, return True.
    :rtype: bool
    """
    with open(path + PLBMNG_CONF, 'r') as config:
        for line in config:
            if re.search('SLICE', line):
                planetlab_slice = re.sub('SLICE="(.*)"', r'\1', line).rstrip()
                if not planetlab_slice:
                    return False
            elif re.search('SSH_KEY', line):
                key = re.sub('SSH_KEY="(.*)"', r'\1', line).rstrip()
                if not key:
                    return False
    return True


def update_last_server_access(info_about_node_dic: dict, chosen_node: list, path: str) -> None:
    """
    Update file which contains all the information about last accessed node by user.

    :param info_about_node_dic: Dictionary which contains all the info about node.
    :type info_about_node_dic: dict
    :param chosen_node: List which contains all information from planetlab\
    network about the node(must follow template from default.node).
    :type chosen_node: list
    :param path: Path to the source directory of plbmng.
    :type path: str
    """
    last_server_file = path + LAST_SERVER
    with open(last_server_file, 'w') as last_server_file:
        last_server_file.write(repr((info_about_node_dic, chosen_node)))


def get_last_server_access(path: str) -> (dict, list):
    """
    Return dictionary and list in tuple with all the available information about the last accessed node.

    :param path: Path to the source directory of plbmng.
    :type path: str
    :return: info_about_node_dic and chosen_node.
    :rtype: tuple
    """
    last_server_file = path + LAST_SERVER
    if not os.path.exists(last_server_file):
        raise FileNotFoundError
    with open(last_server_file, 'r') as last_server_file:
        info_about_node_dic, chosen_node = eval(last_server_file.read().strip('\n'))
    return info_about_node_dic, chosen_node


def server_choices(returned_choice: int, chosen_node: list, info_about_node_dic=None) -> None:
    """
    Prepared choices for user to connect or generate HTML page with map.\
    Based on the :param returned_choice, execute function with given parameters.

    :param returned_choice: Number 1-3 specified by user in DIALOG window.
    :type returned_choice: int
    :param chosen_node: List which contains all information from planetlab\
    network about the node(must follow template from default.node).
    :type chosen_node: list
    :param info_about_node_dic: Dictionary which contains all the info about node.
    :type info_about_node_dic: dict
    :rtype: None
    """
    if returned_choice is None:
        return
    elif not returned_choice:
        return
    elif int(returned_choice) == 1:
        connect(int(returned_choice), chosen_node)
    elif int(returned_choice) == 2:
        connect(int(returned_choice), chosen_node)
    elif int(returned_choice) == 3:
        show_on_map(chosen_node, info_about_node_dic)


def update_availability_database_parent(dialog, nodes=None) -> None:
    """
    Initialize parallel updating of the plbmng database.

    :param dialog: Instance of a dialog engine.
    :param nodes: List of nodes to update the database.
    :type nodes: list
    :rtype: None
    """
    global DIALOG
    increment = Value('f', 0)
    increment.value = float(100 / len(nodes))
    base = Value('f', 0)
    lock = Lock()
    DIALOG = dialog
    dialog.gauge_start()
    try:
        pool = Pool(initializer=multi_processing_init,
                    initargs=(lock, base, increment,))
    except sqlite3.OperationalError:
        dialog.msgbox("Could not update database")
    pool.map(update_availability_database, nodes)
    pool.close()
    pool.join()
    dialog.gauge_update(100, "Completed")
    dialog.gauge_stop()
    dialog.msgbox("Availability database has been successfully updated")


def multi_processing_init(l: Lock, b: Value, i: Value) -> None:
    """
    Initializer for Pool.

    :param l: Lock to synchronize processes.
    :type l: Lock
    :param b: Progress of updating the database. Value is used in DIALOG gauge.
    :type b: Value
    :param i: Incremental value in % added to :param base when process is done.
    :type i: Value
    """
    global lock
    lock = l
    global base
    base = b
    global increment
    increment = i


def update_availability_database(node: list) -> None:
    """
    Update database with given information from :param node.

    :param node: List which contains all information from planetlab\
    network about the node(must follow template from default.node).
    :type node: list
    :rtype: None
    """
    # inint block
    global PLBMNG_DATABASE, DIALOG
    db = sqlite3.connect(get_path() + PLBMNG_DATABASE)
    cursor = db.cursor()
    # action block
    ip_or_hostname = node[2] if node[2] else node[1]
    hash_object = hashlib.md5(ip_or_hostname.encode())
    ssh_result = 'T' if test_ssh(ip_or_hostname) is True else 'F'
    ping_result = 'T' if test_ping(ip_or_hostname, True) is True else 'F'
    ssh = True if ssh_result == 'T' else False
    programs = get_server_params(ip_or_hostname, ssh)
    # find if object exists in the database
    cursor.execute('SELECT nkey from AVAILABILITY where \
                shash = \"' + str(hash_object.hexdigest()) + '\";')
    if cursor.fetchone() is None:
        cursor.execute("INSERT into AVAILABILITY(shash, shostname, bssh, bping) VALUES\
                            (\"" + hash_object.hexdigest() + "\", \"" + ip_or_hostname + "\",\
                            \"" + ssh_result + "\", \"" + ping_result + "\")")
    else:
        cursor.execute("UPDATE availability SET bssh=\"" + ssh_result + "\", bping=\"" +
                       ping_result + "\" WHERE shash=\"" + hash_object.hexdigest() + "\"")

    cursor.execute('SELECT nkey from PROGRAMS where \
                shash = \"' + str(hash_object.hexdigest()) + '\";')
    if cursor.fetchone() is None:
        cursor.execute("INSERT into PROGRAMS(shash, shostname, "
                       "sgcc, spython, skernel, smem) VALUES\
                        (\"" + hash_object.hexdigest() + "\", \"" + ip_or_hostname + "\", \"" + programs[0] + "\",\
                                    \"" + programs[1] + "\", \"" + programs[2] + "\", \"" + programs[3] + "\")")
    else:
        cursor.execute("UPDATE programs SET sgcc=\"" + programs[0] + "\", spython=\"" +
                       programs[1] + "\", skernel=\"" + programs[2] + "\", smem=\"" + programs[
                           3] + "\" WHERE shash=\""
                       + hash_object.hexdigest() + "\"")
    # clean up

    lock.acquire()
    base.value = base.value + increment.value
    DIALOG.gauge_update(int(base.value))
    lock.release()
    db.commit()
    db.close()


def secure_copy(host: str):
    """
    Copy :param SOURCE_PATH to the :param DESTINATION_PATH to :param host. Global parameters must be set first!

    :param host: IP address or host name.
    :type host: str
    :return: Return True if command has failed. Otherwise return False.
    :rtype: bool
    """
    global SOURCE_PATH, DESTINATION_PATH
    ssh_key = get_ssh_key()
    user = get_ssh_user()
    cmd = "scp -r -o PasswordAuthentication=no -o UserKnownHostsFile=/dev/null " \
          "-o StrictHostKeyChecking=no -o LogLevel=QUIET " \
          "-i %s %s %s@%s:%s" % (ssh_key, SOURCE_PATH, user, host, DESTINATION_PATH)
    ret, stdout = run_command(cmd)
    lock.acquire()
    base.value = base.value + increment.value
    DIALOG.gauge_update(int(base.value))
    lock.release()
    if ret != 0:
        return True
    return False


def parallel_copy(dialog, source_path: str, hosts: list, destination_path: str) -> bool:
    """

    :param dialog: Instance of dialog engine.
    :param source_path: File or directory to be copied.
    :type source_path: str
    :param hosts: List of hosts(ip addressed or host names).
    :type hosts: list
    :param destination_path: Path on the target where should be file or directory copied to.
    :type destination_path: str
    :return: True if source path has been copied successfully to all hosts.
    :rtype: bool
    """
    global DIALOG, SOURCE_PATH, DESTINATION_PATH
    DIALOG = dialog
    SOURCE_PATH = source_path
    DESTINATION_PATH = destination_path
    increment = Value('f', 0)
    increment.value = float(100 / len(hosts))
    base = Value('f', 0)
    lock = Lock()
    DIALOG = dialog
    dialog.gauge_start()
    pool = Pool(initializer=multi_processing_init,
                initargs=(lock, base, increment,))
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
