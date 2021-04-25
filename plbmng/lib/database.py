import csv
import hashlib
import re
import sqlite3

from plbmng import executor
from plbmng.lib.library import get_custom_servers
from plbmng.utils.config import get_db_path
from plbmng.utils.logger import logger


class PlbmngDb:
    """
    Class provides basic interaction with plbmng database.
    """

    def __init__(self):
        self._db_path = get_db_path("plbmng_database")
        self.db = sqlite3.connect(self._db_path)
        self.cursor = self.db.cursor()

    @staticmethod
    def init_db_schema():
        try:
            get_db_path("plbmng_database")
        except FileNotFoundError:
            # TODO: use sqlalchemy models here in the future
            db_path = get_db_path("plbmng_database", failsafe=True)
            db = sqlite3.connect(db_path)
            cursor = db.cursor()
            cursor.execute(
                """CREATE TABLE availability(
                                nkey INTEGER PRIMARY KEY,
                                shash TEXT,
                                shostname TEXT,
                                bssh TEXT,
                                bping TEXT
                              )"""
            )
            cursor.execute(
                """CREATE TABLE configuration (
                                id INTEGER PRIMARY KEY,
                                sname TEXT,
                                senabled TEXT
                              )"""
            )
            cursor.execute(
                """CREATE TABLE programs(
                                nkey integer primary key,
                                shash text not null,
                                shostname text not null,
                                sgcc text not null,
                                spython text not null,
                                skernel text not null,
                                smem TEXT
                              )"""
            )
            cursor.execute(
                """CREATE TABLE jobs(
                            id TEXT not null
                                constraint jobs_pk
                                    primary key,
                            node INTEGER
                                constraint jobs_availability_nkey_fk
                                    references availability,
                            cmd_argv TEXT not null,
                            scheduled_at TEXT not null,
                            state INTEGER not null,
                            result INTEGER,
                            started_at TEXT,
                            ended_at TEXT
                          )"""
            )

            # Data
            cursor.execute(
                """INSERT INTO "configuration" ("id","sname","senabled")
                   VALUES (1,'ssh','F'),
                       (2,'ping','F')"""
            )

            nodes = __class__.read_default_node()
            for node in nodes:
                ip_or_hostname = node["dns"] if node["dns"] else node["ip"]
                hash_object = hashlib.md5(ip_or_hostname.encode())
                ssh_result = "F"
                ping_result = "F"

                cursor.execute(
                    "INSERT into availability(shash, shostname, bssh, bping) VALUES("
                    f" '{hash_object.hexdigest()}',"
                    f" '{ip_or_hostname}',"
                    f" '{ssh_result}',"
                    f" '{ping_result}'"
                    ")"
                )
            db.commit()
            db.close()
            return
        logger.error("Database init was not performed. Database already exists.")

    def connect(self) -> None:
        """
        Connect to plbmng database
        """
        self.db = sqlite3.connect(self._db_path)
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

    def get_filters_for_access_servers(self, binary_out=False):
        """
        Return message which filtering options(ssh, ping) are active.

        :rtype: str
        """
        self.cursor.execute("SELECT * from configuration;")
        configuration = self.cursor.fetchall()
        for item in configuration:
            if item[1] == "ssh":
                if item[2] == "T":
                    ssh_filter = True
                else:
                    ssh_filter = False
            elif item[1] == "ping":
                if item[2] == "T":
                    ping_filter = True
                else:
                    ping_filter = False
        if binary_out:
            return {"ssh": ssh_filter, "ping": ping_filter}
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
        if "1" in tag:
            self.cursor.execute('UPDATE configuration SET senabled="T" where sname="ssh"')
            self.db.commit()
        elif "1" not in tag:
            self.cursor.execute('UPDATE configuration SET senabled="F" where sname="ssh"')
            self.db.commit()
        if "2" in tag:
            self.cursor.execute('UPDATE configuration SET senabled="T" where sname="ping"')
            self.db.commit()
        elif "2" not in tag:
            self.cursor.execute('UPDATE configuration SET senabled="F" where sname="ping"')
            self.db.commit()

    def get_nodes(
        self, check_configuration=True, choose_availability_option=None, choose_software_hardware=None, path="/"
    ):
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
            tags = {"1": "gcc", "2": "python", "3": "kernel", "4": "mem"}
            sql = f"SELECT * from programs where s{tags[choose_software_hardware]} not like 'unknown'"
        if choose_availability_option is None and choose_software_hardware is None:
            self.cursor.execute("SELECT * from configuration where senabled='T';")
            configuration = self.cursor.fetchall()
            if not configuration:
                sql = "select shostname from availability"
            else:
                sql = "select shostname from availability where"
                for item in configuration:
                    if re.match(r".*where$", sql):
                        sql = sql + " b" + item[1] + "='T'"
                    else:
                        sql = sql + " and b" + item[1] + "='T'"
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
        lines = self.read_default_node()
        nodes = []
        for line in lines:
            try:
                if check_configuration:
                    if choose_software_hardware:
                        if line["dns"] in server_list.keys():
                            line["gcc"] = server_list[line["dns"]][0]
                            line["python"] = server_list[line["dns"]][1]
                            line["kernel"] = server_list[line["dns"]][2]
                            line["memory"] = server_list[line["dns"]][3]
                            nodes.append(line)
                    else:
                        if line["dns"] in server_list.keys():
                            nodes.append(line)
                else:
                    nodes.append(line)
            except ValueError:
                pass
        last_id = int(line["# id"])
        if not choose_software_hardware:
            nodes.extend(get_custom_servers(last_id))
        return nodes

    @staticmethod
    def read_default_node():
        node_file = get_db_path("default_node")
        nodes = []
        with open(node_file) as tsv:
            csv_reader = csv.DictReader(tsv, delimiter="\t")
            for row in csv_reader:
                row = {k.lower(): v for k, v in row.items()}
                nodes.append(row)
        return nodes

    def add_job(self, job_id, node, cmd_argv, scheduled_at, state, result):
        sql = """INSERT INTO jobs (id, node, cmd_argv, scheduled_at, state, result)
                             values ("{}", (select nkey
                             from availability
                             where shostname = "{}"),  "{}", "{}", {}, {})""".format(
            job_id, node, cmd_argv, scheduled_at, state, result
        )
        self.cursor.execute(sql)
        self.db.commit()

    def update_job(self, job_id, state, result, started_at, ended_at):
        sql = """UPDATE jobs
                 SET state = {jstate}, result = {jresult}, started_at = "{jstarted_at}", ended_at = "{jended_at}"
                 WHERE id = "{jid}";""".format(
            jid=job_id, jstarted_at=started_at, jended_at=ended_at, jstate=state, jresult=result
        )
        # TODO: handle case when any of the time fields might be == null/None
        self.cursor.execute(sql)
        self.db.commit()

    def get_non_stopped_jobs(self):
        selected_columns = ["id", "shostname", "cmd_argv", "scheduled_at", "state", "result", "started_at", "ended_at"]
        sql = """SELECT {}
                 FROM jobs JOIN availability ON jobs.node = availability.nkey
                 WHERE NOT state={}""".format(
            ", ".join(selected_columns), executor.PlbmngJobState["stopped"].value
        )
        self.cursor.execute(sql)
        data = self.cursor.fetchall()
        selected_columns = tuple(selected_columns)
        ns_jobs = []
        # rename shostname -> hostname, id -> job_id
        selected_columns = [x.replace("shostname", "hostname") for x in selected_columns]
        selected_columns = [x.replace("id", "job_id") for x in selected_columns]
        for row in data:
            if len(selected_columns) == len(row):
                args = {selected_columns[i]: row[i] for i, _ in enumerate(row)}
                job = executor.PlbmngJob(**args)
                ns_jobs.append(job)
                # ns_jobs.append({selected_columns[i]: row[i] for i, _ in enumerate(row)})
        return ns_jobs

    # TODO: deduplicate code
    def get_stopped_jobs(self):
        selected_columns = ["id", "shostname", "cmd_argv", "scheduled_at", "state", "result", "started_at", "ended_at"]
        sql = """SELECT {}
                 FROM jobs JOIN availability ON jobs.node = availability.nkey
                 WHERE state={}""".format(
            ", ".join(selected_columns), executor.PlbmngJobState["stopped"].value
        )
        self.cursor.execute(sql)
        data = self.cursor.fetchall()
        selected_columns = tuple(selected_columns)
        s_jobs = []
        # rename shostname -> hostname, id -> job_id
        selected_columns = [x.replace("shostname", "hostname") for x in selected_columns]
        selected_columns = [x.replace("id", "job_id") for x in selected_columns]
        for row in data:
            if len(selected_columns) == len(row):
                args = {selected_columns[i]: row[i] for i, _ in enumerate(row)}
                job = executor.PlbmngJob(**args)
                s_jobs.append(job)
                # ns_jobs.append({selected_columns[i]: row[i] for i, _ in enumerate(row)})
        return s_jobs
