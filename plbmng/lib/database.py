from plbmng.lib.library import get_path, get_custom_servers
import sqlite3
import csv
import re


class PlbmngDb:
    """
    Class provides basic interaction with plbmng database.
    """
    _db_path = '/database/internal.db'

    def __init__(self):
        self.db = sqlite3.connect(get_path() + self._db_path)
        self.cursor = self.db.cursor()

    def connect(self) -> None:
        """
        Connect to plbmng database
        """
        self.db = sqlite3.connect(get_path() + self._db_path)
        self.cursor = self.db.cursor()

    def close(self) -> None:
        """
        Close connection to plbmng database.
        """
        self.db.close()

    def get_stats(self) -> dict:
        """
        Return dictionary which contains stats about ping and ssh responses.

        :rtype: dict
        """
        # Initialize filtering settings
        stat_dic = dict()

        # get numbers of all servers in database
        self.cursor.execute("select count(*) from availability;")
        stat_dic["all"] = self.cursor.fetchall()[0][0]
        # ssh available
        self.cursor.execute("select count(*) from availability where bssh='T';")
        stat_dic["ssh"] = self.cursor.fetchall()[0][0]
        # ping available
        self.cursor.execute("select count(*) from availability where bping='T';")
        stat_dic["ping"] = self.cursor.fetchall()[0][0]

        # clean up block
        return stat_dic

    def get_hw_sw_stats(self) -> dict:
        """
        Return stats how many servers responded with version of kernel, gcc, python and how many RAM server has.

        :rtype: dict
        """
        stat_dic = dict()
        self.cursor.execute("select count(*) from programs;")
        stat_dic["all"] = self.cursor.fetchall()[0][0]
        # ssh available
        self.cursor.execute("select count(*) from programs where sgcc <> 'unknown';")
        stat_dic["gcc"] = self.cursor.fetchall()[0][0]
        # ping available
        self.cursor.execute("select count(*) from programs where spython <> 'unknown';")
        stat_dic["python"] = self.cursor.fetchall()[0][0]
        self.cursor.execute("select count(*) from programs where skernel <> 'unknown';")
        stat_dic["kernel"] = self.cursor.fetchall()[0][0]
        self.cursor.execute("select count(*) from programs where smem <> 'unknown';")
        stat_dic["memory"] = self.cursor.fetchall()[0][0]
        return stat_dic

    def get_filters_for_access_servers(self):
        """
        Return message which filtering options(ssh, ping) are active.

        :rtype: str
        """
        self.cursor.execute('SELECT * from configuration;')
        configuration = self.cursor.fetchall()
        for item in configuration:
            if item[1] == 'ssh':
                if item[2] == 'T':
                    ssh_filter = True
                else:
                    ssh_filter = False
            elif item[1] == 'ping':
                if item[2] == 'T':
                    ping_filter = True
                else:
                    ping_filter = False
        if ssh_filter and ping_filter:
            filter_options = "Only SSH and ICMP available"
        elif ssh_filter and not ping_filter:
            filter_options = "Only SSH available"
        elif not ssh_filter and ping_filter:
            filter_options = "Only PING available"
        else:
            filter_options = "None"
        return filter_options

    def set_filtering_options(self, tag: str) -> None:
        """
        Change filtering options based on given tag.

        :param tag: Number as string. If '1' is given, change ssh to enabled. If '2' is given, change ping to enabled.
        :type tag: str
        """
        if '1' in tag:
            self.cursor.execute(
                'UPDATE configuration SET senabled="T" where sname="ssh"')
            self.db.commit()
        elif '1' not in tag:
            self.cursor.execute(
                'UPDATE configuration SET senabled="F" where sname="ssh"')
            self.db.commit()
        if '2' in tag:
            self.cursor.execute(
                'UPDATE configuration SET senabled="T" where sname="ping"')
            self.db.commit()
        elif '2' not in tag:
            self.cursor.execute(
                'UPDATE configuration SET senabled="F" where sname="ping"')
            self.db.commit()

    def get_nodes(self, check_configuration=True, choose_availability_option=None,
                  choose_software_hardware=None, path="/"):
        """
        Return all nodes from default.node file plus all user specified nodes from user_servers.node.

        :param check_configuration: If set to True, check if status of server has been updated.
        :type check_configuration: bool
        :param choose_availability_option: Select filter option based on availability of ssh, ping or both.
        :type choose_availability_option: int
        :param choose_software_hardware: Select filter option from: gcc, python, kernel, mem.
        :type choose_software_hardware: str
        :param path: Path to the source directory of plbmng.
        :type: str
        :return: List of all nodes
        :rtype: list
        """
        # Initialize filtering settings
        if choose_software_hardware:
            tags = {"1": "gcc",
                    "2": "python",
                    "3": "kernel",
                    "4": "mem"}
            sql = 'SELECT * from programs where s%s not like \'unknown\'' % tags[choose_software_hardware]
        if choose_availability_option is None and choose_software_hardware is None:
            self.cursor.execute('SELECT * from configuration where senabled=\'T\';')
            configuration = self.cursor.fetchall()
            if not configuration:
                sql = 'select shostname from availability'
            else:
                sql = 'select shostname from availability where'
                for item in configuration:
                    if re.match(r'.*where$', sql):
                        sql = sql + ' b' + item[1] + '=\'T\''
                    else:
                        sql = sql + ' and b' + item[1] + '=\'T\''
        elif choose_availability_option == 1:
            sql = "select shostname from availability where bping='T'"
        elif choose_availability_option == 2:
            sql = "select shostname from availability where bssh='T'"
        elif choose_availability_option == 3:
            sql = "select shostname from availability"
        self.cursor.execute(sql)
        returned_values_sql = self.cursor.fetchall()
        server_list = {}
        for item in returned_values_sql:
            if choose_software_hardware:
                server_list[item[2]] = [x for x in item if item.index(x) >= 3]
            else:
                server_list[item[0]] = ""
        # open node file and append to the nodes if the element exists in the server_list
        node_file = path + '/database/default.node'
        nodes = []
        with open(node_file) as tsv:
            lines = csv.reader(tsv, delimiter='\t')
            for line in lines:
                if line[0] == '# ID':
                    continue
                try:
                    if check_configuration:
                        if choose_software_hardware:
                            if line[2] in server_list.keys():
                                tmp = line[:]
                                for i in server_list[line[2]]:
                                    tmp.append(i)
                                nodes.append(tmp)
                        else:
                            if line[2] in server_list.keys():
                                nodes.append(line)
                    else:
                        nodes.append(line)
                except ValueError:
                    pass
            last_id = int(line[-1][0])
        if not choose_software_hardware:
            nodes.extend(get_custom_servers(last_id))
        return nodes
