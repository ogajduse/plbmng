#! /usr/bin/env python3
# Author: Martin Kacmarcik
# License: MIT
# For my Diploma thesis at Faculty of Electrical Engineering -- Brno, University of Technology

import webbrowser
import folium
import subprocess
import signal
import re
import locale
from dialog import Dialog
import hashlib
import sqlite3
from platform import system
from multiprocessing import Pool, Lock, Value
from threading import Timer
import sys
import os
import csv
import shlex

# local imports
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from lib import full_map  # pylint: disable=E0401
from lib import port_scanner  # pylint: disable=E0401t
from lib.planetlab_list_creator import run

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
VERSION = "0.3.8"

# global variables
base = None
increment = None
path = ""

# Initial settings
locale.setlocale(locale.LC_ALL, '')
d = Dialog(dialog="dialog")
d.set_background_title("Planetlab Server Manager " + VERSION)


def signal_handler(sig, frame):
    clear()
    print('Terminating program. You have pressed Ctrl+C')
    exit(1)


def getPath():
    global path
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    path = os.path.dirname(os.path.realpath(__file__))
    return path


def clear():
    os.system("clear")


def testPing(target, returnbool=False):
    pingPacketWaitTime = None
    if system().lower() == 'windows':
        pingParam = '-n'
    else:
        pingParam = '-c'
    # for Linux ping parameter takes seconds while MAC OS ping takes miliseconds
    if system().lower() == 'linux':
        pingPacketWaitTime = 1
    else:
        pingPacketWaitTime = 800
    command = ['ping', pingParam, '1', target, '-W', str(pingPacketWaitTime)]
    p = subprocess.Popen(command, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    # prepare the regular expression to get time
    if system().lower() == 'windows':
        avg = re.compile('Average = ([0-9]+)ms')
    else:
        avg = re.compile(
            'min/avg/max/[a-z]+ = [0-9.]+/([0-9.]+)/[0-9.]+/[0-9.]+')
    avgStr = avg.findall(str(p.communicate()[0]))
    if p.returncode != 0:
        if not returnbool:
            return "Not reachable via ICMP"
        return False
    else:
        p.kill()
        if not returnbool:
            return avgStr[0] + " ms"
        return True


def testSsh(target, printwarn=True):
    result = port_scanner.testPortAvailability(target, 22)
    if (result is True or result is False):
        return result
    elif result is 98:
        if printwarn is True:
            d.msgbox("Hostname could not be resolved. Either the server has been removed, \
                     your network is not working or you have wrongly set DNS.", height=0, width=0)
        return result
    elif result is 97:
        if printwarn is True:
            d.msgbox(
                "Error while connecting to server. Please check your network settings.")
        return result


def verifyApiCredentialsExist():
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


def verifySshCredentialsExist():
    with open(path + "/conf/plbmng.conf", 'r') as config:
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


# parent function to update availability DB that controls multiple processes


def updateAvailabilityDatabaseParent(mode=None):
    if mode == 'cron':
        path = getPath()
    nodes = getNodes(False)
    increment = Value('f', 0)
    increment.value = float(100 / len(nodes))
    base = Value('f', 0)
    lock = Lock()
    d.gauge_start()
    try:
        pool = Pool(25, initializer=multiProcessingInit,
                initargs=(lock, base, increment,))
    except sqlite3.OperationalError:
        d.msgbox("Could not update database")
    pool.map(updateAvailabilityDatabase, nodes)
    pool.close()
    pool.join()
    d.gauge_update(100, "Completed")
    exit_code = d.gauge_stop()
    d.msgbox("Availability database has been successfully updated")


def multiProcessingInit(l, b, i):
    global lock
    lock = l
    global base
    base = b
    global increment
    increment = i


def updateProgressBarMultiProcessing(increment_number):
    global d
    d.gauge_update(int(increment_number))


def updateAvailabilityDatabase(node):
    # inint block
    db = sqlite3.connect('database/internal.db')
    cursor = db.cursor()
    # action block
    ip_or_hostname = node[2] if node[2] else node[1]
    hash_object = hashlib.md5(ip_or_hostname.encode())
    ssh_result = 'T' if testSsh(ip_or_hostname, False) is True else 'F'
    ping_result = 'T' if testPing(ip_or_hostname, True) is True else 'F'
    ssh = True if ssh_result == 'T' else False
    programs = get_servers_programs(ip_or_hostname, ssh)
    # find if object exists in the database
    cursor.execute('SELECT nkey from AVAILABILITY where \
            shash = \"' + str(hash_object.hexdigest()) + '\";')
    if cursor.fetchone() is None:
        # the object yet doesn't exist
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
                       programs[1] + "\", skernel=\"" + programs[2] + "\", smem=\"" + programs[3] + "\" WHERE shash=\""
                       + hash_object.hexdigest() + "\"")
    lock.acquire()
    base.value = base.value + increment.value
    updateProgressBarMultiProcessing(base.value)
    lock.release()
    # clean up
    db.commit()
    db.close()


def getSshKey():
    sshPath = ""
    with open(path + "/conf/plbmng.conf", 'r') as config:
        for line in config:
            if re.search('SSH_KEY', line):
                sshPath = (re.sub('SSH_KEY=', '', line)).rstrip()
    return sshPath


def getSshUser():
    user = ""
    with open(path + "/conf/plbmng.conf", 'r') as config:
        for line in config:
            if re.search('SLICE=', line):
                user = (re.sub('SLICE=', '', line)).rstrip()
    return user


def getUser():
    user = ""
    with open(path + "/conf/plbmng.conf", 'r') as config:
        for line in config:
            if re.search('USERNAME=', line):
                user = (re.sub('USERNAME=', '', line)).rstrip()
    return user


def getStats():
    # Initialize filtering settings
    db = sqlite3.connect('database/internal.db')
    cursor = db.cursor()
    statDic = dict()

    # get numbers of all servers in database
    cursor.execute("select count(*) from availability;")
    statDic["all"] = cursor.fetchall()[0][0]
    # ssh available
    cursor.execute("select count(*) from availability where bssh='T';")
    statDic["ssh"] = cursor.fetchall()[0][0]
    # ping available
    cursor.execute("select count(*) from availability where bping='T';")
    statDic["ping"] = cursor.fetchall()[0][0]

    # clean up block
    db.close()
    return statDic


def get_hw_sw_stats():
    db = sqlite3.connect('database/internal.db')
    cursor = db.cursor()
    statDic = dict()

    # get numbers of all servers in database
    cursor.execute("select count(*) from programs;")
    statDic["all"] = cursor.fetchall()[0][0]
    # ssh available
    cursor.execute("select count(*) from programs where sgcc <> 'unknown';")
    statDic["gcc"] = cursor.fetchall()[0][0]
    # ping available
    cursor.execute("select count(*) from programs where spython <> 'unknown';")
    statDic["python"] = cursor.fetchall()[0][0]
    cursor.execute("select count(*) from programs where skernel <> 'unknown';")
    statDic["kernel"] = cursor.fetchall()[0][0]
    cursor.execute("select count(*) from programs where smem <> 'unknown';")
    statDic["memory"] = cursor.fetchall()[0][0]

    # clean up block
    db.close()
    return statDic


def getPasswd():
    passwd = ""
    with open(path + "/conf/plbmng.conf", 'r') as config:
        for line in config:
            if re.search('PASSWORD=', line):
                passwd = (re.sub('PASSWORD=', '', line)).rstrip()
    return passwd


def getNodes(checkConfiguration=True, chooseAvailabilityOption=None, choose_software_hardware=None):
    # Initialize filtering settings
    db = sqlite3.connect('database/internal.db')
    cursor = db.cursor()
    if choose_software_hardware:
        tags = {"1": "gcc",
                "2": "python",
                "3": "kernel",
                "4": "mem"}
        sql = 'SELECT * from programs where s%s not like \'unknown\'' % tags[choose_software_hardware]
    if chooseAvailabilityOption is None and choose_software_hardware is None:
        cursor.execute('SELECT * from configuration where senabled=\'T\';')
        configuration = cursor.fetchall()
        if not configuration:
            sql = 'select shostname from availability'
        else:
            sql = 'select shostname from availability where'
            for item in configuration:
                if re.match(r'.*where$', sql):
                    sql = sql + ' b' + item[1] + '=\'T\''
                else:
                    sql = sql + ' and b' + item[1] + '=\'T\''
    elif chooseAvailabilityOption == 1:
        sql = "select shostname from availability where bping='T'"
    elif chooseAvailabilityOption == 2:
        sql = "select shostname from availability where bssh='T'"
    elif chooseAvailabilityOption == 3:
        sql = "select shostname from availability"
    cursor.execute(sql)
    returnedValuesSql = cursor.fetchall()
    # convert returned tuples to list
    serverList = {}
    for item in returnedValuesSql:
        if choose_software_hardware:
            serverList[item[2]] = [x for x in item if item.index(x) >= 3]
        else:
            serverList[item[0]] = ""
    # open node file and append to the nodes if the element exists in the serverList
    nodeFile = path + '/database/default.node'
    nodes = []
    with open(nodeFile) as tsv:
        lines = csv.reader(tsv, delimiter='\t')
        for line in lines:
            if line[0] == '# ID':
                continue
            try:
                if checkConfiguration:
                    if choose_software_hardware:
                        if line[2] in serverList.keys():
                            tmp = line[:]
                            for i in serverList[line[2]]:
                                tmp.append(i)
                            nodes.append(tmp)
                    else:
                        if line[2] in serverList.keys():
                            nodes.append(line)
                else:
                    nodes.append(line)
            except ValueError:
                pass
    # This is the worst idea I've ever had.... I need to come up with something better
        last_id = int(line[-1][0])
    if not choose_software_hardware:
        nodes.extend(get_custom_servers(last_id))
    # clean up block
    db.close()
    return nodes


def getAllNodes():
    user = getUser()
    passwd = getPasswd()
    if user != "" and passwd != "":
        os.system("myPwd=$(pwd); cd " + path + "; python3 lib/planetlab_list_creator.py -u \"" +
                  user + "\" -p \"" + passwd + "\" -o ./; cd $(echo $myPwd)")

    else:
        needToFillPasswdFirstInfo()


def isFirstRun():
    isFirst = path + '/database/first.boolean'
    with open(isFirst, 'r') as isFirstFile:
        bIsFirst = isFirstFile.read().strip('\n')
    if bIsFirst == "True":
        with open(isFirst, 'w') as isFirstFile:
            isFirstFile.write("False")
        return True
    else:
        return False


def getFiltersForAccessServers():
    sshFilter = None
    pingFilter = None
    db = sqlite3.connect('database/internal.db')
    cursor = db.cursor()
    cursor.execute('SELECT * from configuration;')
    configuration = cursor.fetchall()
    for item in configuration:
        if item[1] == 'ssh':
            if item[2] == 'T':
                sshFilter = True
            else:
                sshFilter = False
        elif item[1] == 'ping':
            if item[2] == 'T':
                pingFilter = True
            else:
                pingFilter = False
    if sshFilter and pingFilter:
        filterOptions = "Only SSH and ICMP available"
    elif sshFilter and not pingFilter:
        filterOptions = "Only SSH available"
    elif not sshFilter and pingFilter:
        filterOptions = "Only PING available"
    else:
        filterOptions = "None"
    return filterOptions


def lastServerMenu():
    infoAboutNodeDic, chosenNode = getLastServerAccess()
    if infoAboutNodeDic == None:
        return
    returnedChoice = printServerInfo(infoAboutNodeDic)
    if returnedChoice == None:
        return
    elif not returnedChoice:
        return
    elif int(returnedChoice) == 1:
        connect(int(returnedChoice), chosenNode)
    elif int(returnedChoice) == 2:
        connect(int(returnedChoice), chosenNode)
    elif int(returnedChoice) == 3:
        showOnMap(chosenNode, infoAboutNodeDic)


def updateLastServerAccess(infoAboutNodeDic, chosenNode):
    lastServerFile = path + '/database/last_server.node'
    with open(lastServerFile, 'w') as lastServerFile:
        lastServerFile.write(repr((infoAboutNodeDic, chosenNode)))


def getLastServerAccess():
    lastServerFile = path + '/database/last_server.node'
    try:
        with open(lastServerFile, 'r') as lastServerFile:
            infoAboutNodeDic, chosenNode = eval(lastServerFile.read().strip('\n'))
        return infoAboutNodeDic, chosenNode
    except FileNotFoundError:
        d.msgbox("You did not access any server yet.")
        return None, None


def searchNodes(option, regex=None, sw_hw=False):
    answers = []
    choices = []
    counter = 1
    if not sw_hw:
        nodes = getNodes()
    # non-LOCATION search
    if option is not OPTION_LOCATION and not sw_hw:
        for item in nodes:
            if re.search(regex, item[option]):
                answers.append(item)
        if len(answers) == 0:
            returnedChoice = searchNodesGui(False)
        else:
            # prepare choices for GUI
            for item in answers:
                choices.append((str(counter), item[option]))
                counter += 1
            returnedChoice = searchNodesGui(choices)
    # LOCATION based search
    elif sw_hw:
        stats = get_hw_sw_stats()
        code, tag = d.menu("Filter by sofware/hardware:",
                           choices=[("1", "gcc version"),  # - %s" % stats["gcc"]
                                    ("2", "python version"),  # - %s" % stats["python"]
                                    ("3", "kernel version"),  # - %s" % stats["kernel"]
                                    ("4", "total memory"),  # - %s" % stats["memory"]
                                    ])
        if code == d.OK:
            nodes = getNodes(choose_software_hardware=tag)
            index = 10 + int(tag)
            filter_nodes = {}
            for item in nodes:
                if item[index] not in answers:
                    answers.append(item[index])
                    filter_nodes[item[index]] = [item[OPTION_DNS]]
                else:
                    filter_nodes[item[index]].append(item[OPTION_DNS])
            avail_options = sorted(set(answers))
            for item in avail_options:
                choices.append((str(counter), item))
                counter += 1
            returnedChoice = searchNodesGui(choices)
            if returnedChoice == None:
                return
            version = choices[int(returnedChoice) - 1][1]
            choices = []
            counter = 1
            hostnames = sorted(set(filter_nodes[version]))
            for item in hostnames:
                choices.append((str(counter), item))
                counter += 1
            returnedChoice = searchNodesGui(choices)
            if returnedChoice == None:
                return
            else:
                returnedChoice, infoAboutNodeDic, chosenNode = getServerInfo(
                    choices[int(returnedChoice) - 1][1], 0, nodes)
            if returnedChoice == None:
                return
            elif not returnedChoice:
                return
            elif int(returnedChoice) == 1:
                connect(int(returnedChoice), chosenNode)
            elif int(returnedChoice) == 2:
                connect(int(returnedChoice), chosenNode)
            elif int(returnedChoice) == 3:
                showOnMap(chosenNode, infoAboutNodeDic)
            return
        else:
            return
    else:
        for item in nodes:
            answers.append(item[OPTION_CONTINENT])
        continents = sorted(set(answers))
        # prepare choices for GUI
        for item in continents:
            choices.append((str(counter), item))
            counter += 1
        returnedChoice = searchNodesGui(choices)
        if returnedChoice == None:
            return
        answers = []
        choices = []
        counter = 1
        for item in nodes:
            if re.search(continents[int(returnedChoice) - 1], item[OPTION_CONTINENT]):
                answers.append(item[OPTION_COUNTRY])
        countries = sorted(set(answers))
        # prepare choices for GUI
        for item in countries:
            choices.append((str(counter), item))
            counter += 1
        returnedChoice = searchNodesGui(choices)
        if returnedChoice == None:
            return
        answers = []
        choices = []
        counter = 1
        for item in nodes:
            if re.search(countries[int(returnedChoice) - 1], item[OPTION_COUNTRY]):
                answers.append(item[OPTION_DNS])
        hostnames = sorted(set(answers))
        # prepare choices for GUI
        for item in hostnames:
            choices.append((str(counter), item))
            counter += 1
        returnedChoice = searchNodesGui(choices)
    if returnedChoice == None:
        return
    else:
        returnedChoice, infoAboutNodeDic, chosenNode = getServerInfo(
            choices[int(returnedChoice) - 1][1], option, nodes)
    if returnedChoice == None:
        return
    elif not returnedChoice:
        return
    elif int(returnedChoice) == 1:
        connect(int(returnedChoice), chosenNode)
    elif int(returnedChoice) == 2:
        connect(int(returnedChoice), chosenNode)
    elif int(returnedChoice) == 3:
        showOnMap(chosenNode, infoAboutNodeDic)


def connect(mode, node):
    clear()
    key = getSshKey()
    user = getSshUser()
    if mode == 1:
        return_value = os.system(
            "ssh -o \"StrictHostKeyChecking = no\" -o \"UserKnownHostsFile=\
            /dev/null\" -i " + key + " " + user + "@" + node[OPTION_IP])
        if return_value is not 0:
            d.msgbox("Error while connecting. Please verify your credentials.")
    elif mode == 2:
        os.system('ssh-add ' + key)
        return_value = os.system("mc sh://" + user + "@" + node[OPTION_IP] + ":/home")
        if return_value is not 0:
            d.msgbox("Error while connecting. Please verify your credentials.")
    else:
        return


def showOnMap(node, nodeInfo=""):
    _stderr = os.dup(2)
    os.close(2)
    _stdout = os.dup(1)
    os.close(1)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 2)
    os.dup2(fd, 1)

    latitude = float(node[-2])
    longitude = float(node[-1])
    name = node[OPTION_DNS]
    popup = folium.Popup(nodeInfo["text"].strip().replace('\n', '<br>'), max_width=1000)
    nodeMap = folium.Map(location=[latitude, longitude],
                         zoom_start=2, min_zoom=2)
    if nodeInfo == "":
        folium.Marker([latitude, longitude], popup=popup).add_to(nodeMap)
    else:
        folium.Marker([latitude, longitude], popup).add_to(nodeMap)
    nodeMap.save('/tmp/map_plbmng.html')
    try:
        webbrowser.get().open('file://' + os.path.realpath('/tmp/map_plbmng.html'))
    finally:
        os.close(fd)
        os.dup2(_stderr, 2)
        os.dup2(_stdout, 1)


def plotServersOnMap(mode):
    _stderr = os.dup(2)
    os.close(2)
    _stdout = os.dup(1)
    os.close(1)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 2)
    os.dup2(fd, 1)

    # update base_data.txt file based on latest database with nodes
    nodes = getNodes(True, int(mode))
    full_map.plot_server_on_map(nodes)
    mapFile = "plbmng_server_map.html"
    try:
        webbrowser.get().open('file://' + os.path.realpath(path + "/" + mapFile))
    finally:
        os.close(fd)
        os.dup2(_stderr, 2)
        os.dup2(_stdout, 1)


def getServerInfo(serverId, option, nodes=None):
    if nodes == None:
        nodes = getNodes()
    if option == 0:
        option = OPTION_DNS
    if isinstance(serverId, str):
        # in nodes find the chosenOne node
        chosenOne = ""
        for item in nodes:
            if re.search(serverId, item[option]):
                chosenOne = item
                break
        if chosenOne == "":
            print("Internal error, please file a bug report via PyPi")
            exit(99)
        # get information about servers
        ip_or_hostname = chosenOne[OPTION_DNS] if chosenOne[OPTION_DNS] != "unknown" else chosenOne[OPTION_IP]
        infoAboutNodeDic = dict()
        region, city, url, fullname, lat, lon = getInfoFromNode(chosenOne)
        infoAboutNodeDic["region"] = region
        infoAboutNodeDic["city"] = city
        infoAboutNodeDic["url"] = url
        infoAboutNodeDic["fullname"] = fullname
        infoAboutNodeDic["lat"] = lat
        infoAboutNodeDic["lon"] = lon
        infoAboutNodeDic["icmp"] = testPing(ip_or_hostname)
        infoAboutNodeDic["sshAvailable"] = testSsh(ip_or_hostname)
        programs = get_servers_programs(ip_or_hostname, infoAboutNodeDic["sshAvailable"])
        infoAboutNodeDic["text"] = """
            NODE: %s
            IP: %s
            CONTINENT: %s, COUNTRY: %s, REGION: %s, CITY: %s
            URL: %s
            FULL NAME: %s
            LATITUDE: %s, LONGITUDE: %s
            CURRENT ICMP RESPOND: %s
            CURRENT SSH AVAILABILITY: %r
            GCC version: %s Python: %s Kernel version: %s
            """ % (chosenOne[OPTION_DNS],
                   chosenOne[OPTION_IP],
                   chosenOne[OPTION_CONTINENT],
                   chosenOne[OPTION_COUNTRY],
                   infoAboutNodeDic["region"],
                   infoAboutNodeDic["city"],
                   infoAboutNodeDic["url"],
                   infoAboutNodeDic["fullname"],
                   infoAboutNodeDic["lat"],
                   infoAboutNodeDic["lon"],
                   infoAboutNodeDic["icmp"],
                   infoAboutNodeDic["sshAvailable"],
                   programs[0],
                   programs[1],
                   programs[2])
        if infoAboutNodeDic["sshAvailable"] is True or infoAboutNodeDic["sshAvailable"] is False:
            # update last server access database
            updateLastServerAccess(infoAboutNodeDic, chosenOne)
            return printServerInfo(infoAboutNodeDic), infoAboutNodeDic, chosenOne
        else:
            return False, False, False


def getInfoFromNode(node):
    region = node[5]
    city = node[6]
    url = node[7]
    fullname = node[8]
    lat = node[9]
    lon = node[10]
    return region, city, url, fullname, lat, lon


def removeCron():
    os.system("crontab -l | grep -v \"plbmng crontab\" | crontab -")


def addToCron(mode):
    if int(mode) == 1:
        line = "@daily plbmng crontab"
    elif int(mode) == 2:
        line = "@weekly plbmng crontab"
    elif int(mode) == 3:
        line = "@monthly plbmng crontab"
    os.system("echo \"$(crontab -l ; echo " + line + ")\" | crontab -")


###################
#  GUI functions  #
###################


def printServerInfo(infoAboutNodeDic):
    if not verifySshCredentialsExist():
        preparedChoices = [("1", "Connect via SSH (Credentials not set!)"),
                           ("2", "Connect via MC (Credentials not set!)"),
                           ("3", "Show on map")]
    else:
        preparedChoices = [("1", "Connect via SSH"),
                           ("2", "Connect via MC"),
                           ("3", "Show on map")]
    code, tag = d.menu(
        infoAboutNodeDic["text"], height=0, width=0, menu_height=0, choices=preparedChoices)
    if code == d.OK:
        return tag
    else:
        return None


def searchNodesGui(prepared_choices):
    if not prepared_choices:
        d.msgbox("No results found.", width=0, height=0)
        return None
    while True:
        code, tag = d.menu("These are the results:",
                           choices=prepared_choices,
                           title="Search results")
        if code == d.OK:
            return tag
        else:
            return None


def firstRunMessage():
    d.msgbox(
        "This is your first run of the application. Please go to 'Set Credentials' menu and set your credentials now.",
        height=0, width=0)


def needToFillPasswdFirstInfo():
    d.msgbox("Credentials are not set. Please go to menu and set them now")


def initInterface():
    getPath()
    signal.signal(signal.SIGINT, signal_handler)
    if isFirstRun():
        firstRunMessage()
    while True:
        # Main menu
        code, tag = d.menu("Choose one of the following options:",
                           choices=[("1", "Access servers"),
                                    ("2", "Monitor servers"),
                                    ("3", "Plot servers on map"),
                                    ("4", "Set credentials"),
                                    ("5", "Statistics"),
                                    ("6", "Add server"),
                                    ("7", "About")],
                           title="MAIN MENU")

        if code == d.OK:
            # Acess servers
            if tag == "1":
                accessServersGui()
            # Meausre servers
            elif tag == "2":
                monitorServersGui()
            # Plot servers on map
            elif tag == "3":
                plotServersOnMapGui()
            # Set crdentials
            elif tag == "4":
                setCredentialasGui()
            elif tag == "5":
                statsGui()
            elif tag == "6":
                addCustomServerMenu()
            elif tag == "7":
                aboutGui()
        else:
            clear()
            exit(0)


def setCredentialasGui():
    code, text = d.editbox(path + '/conf/plbmng.conf', height=0, width=0)
    if code == d.OK:
        with open(path + '/conf/plbmng.conf', "w") as configFile:
            configFile.write(text)


def filteringOptionsGui():
    # inint the database to pull configuration data
    db = sqlite3.connect('database/internal.db')
    cursor = db.cursor()
    cursor.execute("select senabled from configuration where sname='ssh'")
    ssh_enabled = True if cursor.fetchone()[0] == 'T' else False
    cursor.execute("select senabled from configuration where sname='ping'")
    ping_enabled = True if cursor.fetchone()[0] == 'T' else False
    # Render the GUI
    code, t = d.checklist(
        "Press SPACE key to choose filtering options", height=0, width=0, list_height=0,
        choices=[("1", "Enable SSH accessible machines", ssh_enabled),
                 ("2", "Enable PING accessible machines", ping_enabled)], )
    # Detect changes using simple combination and update the database based on result
    if '1' in t and not ssh_enabled:
        cursor.execute(
            'UPDATE configuration SET senabled="T" where sname="ssh"')
        db.commit()
    elif '1' not in t and ssh_enabled:
        cursor.execute(
            'UPDATE configuration SET senabled="F" where sname="ssh"')
        db.commit()
    if '2' in t and not ping_enabled:
        cursor.execute(
            'UPDATE configuration SET senabled="T" where sname="ping"')
        db.commit()
    elif '2' not in t and ping_enabled:
        cursor.execute(
            'UPDATE configuration SET senabled="F" where sname="ping"')
        db.commit()
    # Clean up database
    db.close()


def statsGui():
    statsDic = getStats()
    d.msgbox("""
    Servers in database: """ + str(statsDic["all"]) + """
    Ssh available: """ + str(statsDic["ssh"]) + """
    Ping available: """ + str(statsDic["ping"]) + """
    """, width=0, height=0, title="Current statistics from last update of servers status:")


def aboutGui():
    d.msgbox("""
            PlanetLab Server Manager
            Project supervisor:
                Dan Komosny
            Authors:
                Tomas Andrasov
                Filip Suba
                Martin Kacmarcik

            Version """ + VERSION + """
            This application is under MIT license.
            """, width=0, height=0, title="About")


# Plot servers on map part of GUI


def plotServersOnMapGui():
    while True:
        code, tag = d.menu("Choose one of the following options:",
                           choices=[("1", "Plot servers reponding to ping"),
                                    ("2", "Plot ssh available servers"),
                                    ("3", "Plot all servers")],
                           title="Map menu")
        if code == d.OK:
            plotServersOnMap(tag)
            return
        else:
            return


# Monitor servers part of GUI


def monitorServersGui():
    if not verifyApiCredentialsExist():
        d.msgbox(
            "Warning! Your credentials for PlanetLab API are not set. Please use 'Set credentials' option in main menu to set them.")
    while True:
        code, tag = d.menu("Choose one of the following options:",
                           choices=[("1", "Set crontab for status update"),
                                    ("2", "Update server list now"),
                                    ("3", "Update server status now")],
                           title="Monitoring menu", height=0, width=0)
        if code == d.OK:
            if tag == "1":
                code, tag = d.menu("Choose one of the following options:",
                                   choices=[("1", "Set monitoring daily"),
                                            ("2", "Set monitoring weekly"),
                                            ("3", "Set monitoring monthly"),
                                            ("4", "Remove all monitoring from cron")],
                                   title="Crontab menu")
                if code == d.OK:
                    if tag == "1":
                        addToCron(tag)
                    elif tag == "2":
                        addToCron(tag)
                    elif tag == "3":
                        addToCron(tag)
                    elif tag == "4":
                        removeCron()
                else:
                    continue
            elif tag == "2":
                if d.yesno("This is going to take around 20 minutes") == d.OK:
                    getAllNodes()
                else:
                    continue
            elif tag == "3":
                if d.yesno("This can take few minutes. Do you want to continue?") == d.OK:
                    if not verifySshCredentialsExist():
                        d.msgbox(
                            "Error! Your ssh credentials are not set. Please use 'Set credentials' option in main menu to set them.")
                        continue
                    else:
                        updateAvailabilityDatabaseParent()
                else:
                    continue
        else:
            return


# Acess servers part of GUI
def accessServersGui():
    while True:
        filterOptions = getFiltersForAccessServers()
        menuText = """
        \nActive filters: """ + filterOptions

        code, tag = d.menu("Choose one of the following options:" + menuText,
                           choices=[
                               ("1", "Filtering options"),
                               ("2", "Access last server"),
                               ("3", "Serach by DNS"),
                               ("4", "Search by IP"),
                               ("5", "Search by location"),
                               ("6", "Search by available software/hardware")],
                           title="ACCESS SERVERS")
        if code == d.OK:
            # Filtering options
            if tag == "1":
                filteringOptionsGui()
            # Access last server
            elif tag == "2":
                lastServerMenu()
            elif tag == "3":
                code, answer = d.inputbox("Search for:" + menuText, title="Search", width=0, height=0)
                if code == d.OK:
                    searchNodes(OPTION_DNS, answer)
                else:
                    continue
            # Search by IP
            elif tag == "4":
                code, answer = d.inputbox("Search for:" + menuText, title="Search", width=0, height=0)
                if code == d.OK:
                    searchNodes(OPTION_IP, answer)
                else:
                    continue
            # Search by location
            elif tag == "5":
                # Grepuje se default node
                searchNodes(OPTION_LOCATION)
            elif tag == "6":
                searchNodes(OPTION_PYTHON, sw_hw=True)
        else:
            return


# TODO:IN DEVELOPMENT
def get_custom_servers(start_id):
    user_nodes = []
    with open(path + "/database/user_servers.node") as tsv:
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


def addCustomServerMenu():
    code, text = d.editbox(path + '/database/user_servers.node', height=0, width=0)
    if code == d.OK:
        with open(path + '/database/user_servers.node', "w") as nodeFile:
            nodeFile.write(text)


def run_command(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
    timer = Timer(2, p.kill)
    try:
        timer.start()
        stdout, stderr = p.communicate()
        stdout = stdout.decode('ascii', 'ignore')
        stdout = stdout.rstrip("\n")
        retcode = p.returncode
    finally:
        timer.cancel()
    p.kill()
    return retcode, stdout


def get_servers_programs(ip_or_hostname, ssh=False):
    commands = ["gcc -dumpversion", "python3 --version", "uname -r",
                "grep MemTotal /proc/meminfo | awk '{print $2 / 1024}'",
                ]
    if not ssh:
        # return list of unknown string depending on number of commands
        return ["unknown" for x in range(len(commands))]
    cmd = 'ssh -o PasswordAuthentication=no -o UserKnownHostsFile=/dev/null ' \
          '-o StrictHostKeyChecking=no -o LogLevel=QUIET -i %s %s@%s ' % (getSshKey(), getSshUser(), ip_or_hostname)
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


if __name__ == "__main__":
    initInterface()
    exit(0)
