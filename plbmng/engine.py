#! /usr/bin/env python3
# Author: Martin Kacmarcik


import os
import sys
import signal
import locale
from dialog import Dialog
from datetime import datetime
from plbmng.lib.database import PlbmngDb
from plbmng.lib.library import update_availability_database_parent, plot_servers_on_map, \
    verify_ssh_credentials_exist, verify_api_credentials_exist, is_first_run, get_all_nodes, \
    clear, get_path, get_ssh_user, parallel_copy, OPTION_DNS, OPTION_IP, get_last_server_access, \
    server_choices, OPTION_GCC, OPTION_KERNEL, OPTION_PYTHON, OPTION_MEM, search_by_sware_hware, \
    get_server_info, search_by_location, search_by_regex, NeedToFillPasswdFirstInfo

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))


class Engine:
    """
    Class used for the interaction with the user and decision making based on user's input.
    """
    VERSION = "0.4.2"
    _conf_path = '/conf/plbmng.conf'
    user_nodes = '/database/user_servers.node'
    path = ""
    _debug = False
    _filtering_options = None

    def __init__(self):
        self.d = Dialog(dialog="dialog")
        self.db = PlbmngDb()
        locale.setlocale(locale.LC_ALL, '')
        self.d.set_background_title("Planetlab Server Manager " + self.VERSION)
        self.path = get_path()

    def _log_message(self, msg) -> None:
        """
        Write :param message to the plbmng log file.

        :param msg: Message to be written into the log file.
        :type: str
        """
        with open(self.path + "/logs/plbmng.log", "a") as log:
            log.write("[%s] INFO: %s\n" % (datetime.now(), msg))

    def init_interface(self) -> None:
        """
        Main function of Engine class. Will show root page of plbmng.
        """

        def signal_handler(sig, frame):
            clear()
            print('Terminating program. You have pressed Ctrl+C')
            exit(1)

        signal.signal(signal.SIGINT, signal_handler)
        if is_first_run():
            self.first_run_message()
        while True:
            # Main menu
            code, tag = self.d.menu("Choose one of the following options:",
                                    choices=[("1", "Access servers"),
                                             ("2", "Monitor servers"),
                                             ("3", "Plot servers on map"),
                                             ("4", "Set credentials"),
                                             ("5", "Extras")],
                                    title="MAIN MENU")

            if code == self.d.OK:
                # Access servers
                if tag == "1":
                    self.access_servers_gui()
                # Measure servers
                elif tag == "2":
                    self.monitor_servers_gui()
                # Plot servers on map
                elif tag == "3":
                    self.plot_servers_on_map_gui()
                # Set credentials
                elif tag == "4":
                    self.set_credentials_gui()
                elif tag == "5":
                    self.extras_menu()
            else:
                clear()
                exit(0)

    def extras_menu(self):
        """
        Extras menu
        """
        code, tag = self.d.menu("Choose one of the following options:",
                                choices=[("1", "Add server to database"),
                                         ("2", "Copy files to server/servers"),
                                         ("3", "Statistics"),
                                         ("4", "About"), ],
                                title="EXTRAS")
        if code == self.d.OK:
            if tag == "1":
                self.add_external_server_menu()
            elif tag == "2":
                self.copy_file()
            elif tag == "3":
                self.stats_gui(self.db.get_stats())
            elif tag == "3":
                self.about_gui(self.VERSION)

    def get_conf_path(self) -> str:
        """
        Return path to the plbmng config file.

        :rtype: str
        """
        return self._conf_path

    def set_credentials_gui(self) -> None:
        """
        Credentials Menu.
        """
        code, text = self.d.editbox(self.path + self.get_conf_path(), height=0, width=0)
        if code == self.d.OK:
            with open(self.path + self.get_conf_path(), "w") as configFile:
                configFile.write(text)

    def filtering_options_gui(self) -> int:
        """
        Filtering options menu.

        :return: Code based on PING AND SSH values.
        :rtype: int
        """
        code, t = self.d.checklist(
            "Press SPACE key to choose filtering options", height=0, width=0, list_height=0,
            choices=[("1", "Enable SSH accessible machines", False),
                     ("2", "Enable PING accessible machines", False)], )

        if self.d.OK:
            self.db.set_filtering_options(t)
            if len(t) == 2:
                return 3
            elif '1' in t:
                return 1
            elif '2' in t:
                return 2
        return None

    def stats_gui(self, stats_dic: dict) -> None:
        """
        Stats menu.

        :param stats_dic: Dictionary which contains number of servers in database,\
        number of servers which responded to the ping or ssh check.
        :type stats_dic: dict
        """
        self.d.msgbox("""
        Servers in database: """ + str(stats_dic["all"]) + """
        Ssh available: """ + str(stats_dic["ssh"]) + """
        Ping available: """ + str(stats_dic["ping"]) + """
        """, width=0, height=0, title="Current statistics from last update of servers status:")

    def about_gui(self, version):
        """
        About menu.

        :param version: Current version of plbmng.
        :type version: str
        """
        self.d.msgbox("""
                PlanetLab Server Manager
                Project supervisor:
                    Dan Komosny
                Authors:
                    Tomas Andrasov
                    Filip Suba
                    Martin Kacmarcik

                Version """ + version + """
                This application is under MIT license.
                """, width=0, height=0, title="About")

    def plot_servers_on_map_gui(self):
        """
        Plot servers on map menu.
        """
        while True:
            code, tag = self.d.menu("Choose one of the following options:",
                                    choices=[("1", "Plot servers responding to ping"),
                                             ("2", "Plot ssh available servers"),
                                             ("3", "Plot all servers")],
                                    title="Map menu")
            if code == self.d.OK:
                nodes = self.db.get_nodes(True, int(tag), path=self.path)
                plot_servers_on_map(nodes, self.path)
                return
            else:
                return

    def monitor_servers_gui(self):
        """
        Monitor servers menu.
        """
        if not verify_api_credentials_exist(self.path):
            self.d.msgbox(
                "Warning! Your credentials for PlanetLab API are not set. "
                "Please use 'Set credentials' option in main menu to set them.")
        while True:
            code, tag = self.d.menu("Choose one of the following options:",
                                    # ("1", "Set crontab for status update"),
                                    choices=[("1", "Update server list now"),
                                             ("2", "Update server status now")],
                                    title="Monitoring menu", height=0, width=0)
            if code == self.d.OK:
                """if tag == "1":
                    code, tag = self.d.menu("Choose one of the following options:",
                                       choices=[("1", "Set monitoring daily"),
                                                ("2", "Set monitoring weekly"),
                                                ("3", "Set monitoring monthly"),
                                                ("4", "Remove all monitoring from cron")],
                                       title="Crontab menu")
                    if code == self.d.OK:
                        if tag == "1":
                            addToCron(tag)
                        elif tag == "2":
                            addToCron(tag)
                        elif tag == "3":
                            addToCron(tag)
                        elif tag == "4":
                            removeCron()
                    else:
                        continue"""
                if tag == "1":
                    if self.d.yesno("This is going to take around 20 minutes") == self.d.OK:
                        try:
                            get_all_nodes()
                        except NeedToFillPasswdFirstInfo:
                            self.d.msgbox(
                                "Error! Your Planetlab credentials are not set. "
                                "Please use 'Set credentials' option in main menu to set them.")
                    else:
                        continue
                elif tag == "2":
                    if self.d.yesno("This can take few minutes. Do you want to continue?") == self.d.OK:
                        if not verify_ssh_credentials_exist(self.path):
                            self.d.msgbox(
                                "Error! Your ssh credentials are not set. "
                                "Please use 'Set credentials' option in main menu to set them.")
                            continue
                        else:
                            nodes = self.db.get_nodes(path=self.path)
                            self.db.close()
                            update_availability_database_parent(dialog=self.d, nodes=nodes)
                            self.db.connect()
                    else:
                        continue
            else:
                return

    def copy_file(self):
        """
        Copy files to servers menu.
        """
        text = "Type in destination path on the target/targets."
        init = "/home/" + get_ssh_user()
        code, source_path = self.d.fselect(filepath="/home/", height=10, width=0)
        if code == self.d.OK:
            servers = self.access_servers_gui(checklist=True)
        else:
            return
        if not servers:
            self.d.msgbox("You did not select any servers!")
            return
        code, destination_path = self.d.inputbox(text=text, init=init, height=0, width=0)
        if code == self.d.OK:
            ret = parallel_copy(dialog=self.d, source_path=source_path,
                                hosts=servers, destination_path=destination_path)
        else:
            return
        if ret:
            self.d.msgbox("Copy successful!")
            return
        self.d.msgbox("Could not copy file/directory to the all servers!")
        return

    def access_servers_gui(self, checklist=False):
        """
        Access servers menu.

        :param checklist: True if menu shows filtered option as checkboxes.
        :type checklist: bool
        :return: If checklist is True, return all chosen servers by user.
        :rtype: list
        """
        while True:
            filter_options = self.db.get_filters_for_access_servers()
            menu_text = """
            \nActive filters: """ + filter_options

            code, tag = self.d.menu("Choose one of the following options:" + menu_text,
                                    choices=[
                                        ("1", "Filtering options"),
                                        ("2", "Access last server"),
                                        ("3", "Serach by DNS"),
                                        ("4", "Search by IP"),
                                        ("5", "Search by location"),
                                        ("6", "Search by available software/hardware")],
                                    title="ACCESS SERVERS")
            if code == self.d.OK:
                # Filtering options
                nodes = self.db.get_nodes(path=self.path, choose_availability_option=self._filtering_options)
                if tag == "1":
                    self._filtering_options = self.filtering_options_gui()
                # Access last server
                elif tag == "2":
                    self.last_server_menu()
                elif tag == "3":
                    ret = self.search_by_regex_menu(nodes, OPTION_DNS, checklist)
                    if checklist:
                        return ret
                # Search by IP
                elif tag == "4":
                    ret = self.search_by_regex_menu(nodes, OPTION_IP, checklist)
                    if checklist:
                        return ret
                # Search by location
                elif tag == "5":
                    # Grepuje se default node
                    ret = self.search_by_location_menu(nodes, checklist)
                    if checklist:
                        return ret
                elif tag == "6":
                    ret = self.advanced_filtering_menu(checklist)
                    if checklist:
                        return ret
            else:
                return

    def print_server_info(self, info_about_node_dic: dict):
        """
        Print server info menu.

        :param info_about_node_dic: Dictionary which contains all the info about node.
        :type info_about_node_dic: dict
        """
        if not verify_ssh_credentials_exist(self.path):
            prepared_choices = [("1", "Connect via SSH (Credentials not set!)"),
                                ("2", "Connect via MC (Credentials not set!)"),
                                ("3", "Show on map")]
        else:
            prepared_choices = [("1", "Connect via SSH"),
                                ("2", "Connect via MC"),
                                ("3", "Show on map")]
        code, tag = self.d.menu(
            info_about_node_dic["text"], height=0, width=0, menu_height=0, choices=prepared_choices)
        if code == self.d.OK:
            return tag
        else:
            return None

    def search_nodes_gui(self, prepared_choices, checklist=False):
        """
        Search nodes menu.

        :param prepared_choices: list of prepared choices for user.
        :type prepared_choices: list
        :param checklist: If checklist is True, crate checklist instead of menu(multiple choices).
        :type checklist: bool
        :return: Selected tag(s) from :param prepared choices.
        """
        if not prepared_choices:
            self.d.msgbox("No results found", width=0, height=0)
            return None
        while True:
            if not checklist:
                code, tag = self.d.menu("These are the results:",
                                        choices=prepared_choices,
                                        title="Search results")
            else:
                code, tag = self.d.checklist("These are the results:",
                                             choices=prepared_choices,
                                             title="Search results")
            if code == self.d.OK:
                return tag
            else:
                return None

    def first_run_message(self) -> None:
        """
        First run menu.
        """
        self.d.msgbox(
            "This is first run of the application. "
            "Please go to 'Set Credentials' menu and set your credentials now.",
            height=0, width=0)

    def need_to_fill_passwd_first_info(self):
        """
        Need to fill in password first menu.
        """
        self.d.msgbox("Credentials are not set. Please go to menu and set them now")

    def add_external_server_menu(self):
        """
        Add external server into the plbmng database(NOT TO THE PLANETLAB NETWORK!).
        """
        code, text = self.d.editbox(self.path + self.user_nodes, height=0, width=0)
        if code == self.d.OK:
            with open(self.path + self.user_nodes, "w") as nodeFile:
                nodeFile.write(text)

    def last_server_menu(self) -> None:
        """
        Return last accessed server menu.
        """
        info_about_node_dic = None
        chosen_node = None
        try:
            info_about_node_dic, chosen_node = get_last_server_access(self.path)
        except FileNotFoundError:
            self.d.msgbox("You did not access any server yet.")
        if info_about_node_dic is None or chosen_node is None:
            return
        returned_choice = self.print_server_info(info_about_node_dic)
        server_choices(returned_choice, chosen_node, info_about_node_dic)

    def advanced_filtering_menu(self, checklist: bool):
        """
        Advanced filtering menu.

        :param checklist: If checklist is True, return all chosen servers by user.
        :type checklist: bool
        """
        code, tag = self.d.menu("Filter by software/hardware:",
                                choices=[("1", "gcc version"),  # - %s" % stats["gcc"]
                                         ("2", "python version"),  # - %s" % stats["python"]
                                         ("3", "kernel version"),  # - %s" % stats["kernel"]
                                         ("4", "total memory"),  # - %s" % stats["memory"]
                                         ])
        if code == self.d.OK:
            nodes = self.db.get_nodes(choose_software_hardware=tag, path=self.path)
            answers = None
            if tag == "1":
                answers = search_by_sware_hware(nodes=nodes, option=OPTION_GCC)
            elif tag == "2":
                answers = search_by_sware_hware(nodes=nodes, option=OPTION_PYTHON)
            elif tag == "3":
                answers = search_by_sware_hware(nodes=nodes, option=OPTION_KERNEL)
            elif tag == "4":
                answers = search_by_sware_hware(nodes=nodes, option=OPTION_MEM)
            if not answers:
                return
            choices = [(item, "") for item in answers.keys()]
            returned_choice = self.search_nodes_gui(choices)
            if returned_choice is None:
                return
            hostnames = sorted(set(answers[returned_choice]))
            if not checklist:
                choices = [(hostname, "") for hostname in hostnames]
            else:
                choices = [(hostname, "", False) for hostname in hostnames]
            returned_choice = self.search_nodes_gui(choices, checklist)
            if checklist:
                return returned_choice
            if returned_choice is None:
                return
            else:
                info_about_node_dic, chosen_node = get_server_info(returned_choice, OPTION_DNS, nodes)
                if not info_about_node_dic:
                    self.d.msgbox("Server is unreachable. Please update server status.")
                    return
                returned_choice = self.print_server_info(info_about_node_dic)
            try:
                server_choices(returned_choice, chosen_node, info_about_node_dic)
            except ConnectionError as err:
                self.d.msgbox("Error while connecting. Please verify your credentials.")
                self._log_message(err)
        else:
            return

    def search_by_location_menu(self, nodes, checklist: bool):
        """
        Search by location menu.

        :param checklist: If checklist is True, return all chosen servers by user.
        :type checklist: bool
        """
        continents, countries = search_by_location(nodes)
        choices = [(continent, "") for continent in sorted(continents.keys())]
        returned_choice = self.search_nodes_gui(choices)
        if returned_choice is None:
            return
        choices = [(country, "") for country in countries.keys() if country in continents[returned_choice]]
        returned_choice = self.search_nodes_gui(choices)
        if returned_choice is None:
            return
        if not checklist:
            choices = [(item, "") for item in sorted(countries[returned_choice])]
        else:
            choices = [(item, "", False) for item in sorted(countries[returned_choice])]
        returned_choice = self.search_nodes_gui(choices, checklist)
        if checklist:
            return returned_choice
        if returned_choice is None:
            return
        info_about_node_dic, chosen_node = get_server_info(returned_choice, OPTION_DNS, nodes)
        if not info_about_node_dic:
            self.d.msgbox("Server is unreachable. Please update server status.")
            return
        returned_choice = self.print_server_info(info_about_node_dic)
        try:
            server_choices(returned_choice, chosen_node, info_about_node_dic)
        except ConnectionError as err:
            self.d.msgbox("Error while connecting. Please verify your credentials.")
            self._log_message(err)

    def search_by_regex_menu(self, nodes: list, option: int, checklist: bool):
        """
        Search by regex menu.

        :param nodes: List of all available nodes.
        :type nodes: list
        :param option: Index in the nodes list(check constants at the start of this file).
        :type option: int
        :param checklist: If checklist is True, return all chosen servers by user.
        :type checklist: bool
        """
        code, answer = self.d.inputbox("Search for:", title="Search", width=0, height=0)
        if code == self.d.OK:
            answers = search_by_regex(nodes, option=option, regex=answer)
            if not checklist:
                choices = [(item, "") for item in answers]
            else:
                choices = [(item, "", False) for item in answers]
            returned_choice = self.search_nodes_gui(choices, checklist)
            if checklist:
                return returned_choice
            if returned_choice is None:
                return
            else:
                info_about_node_dic, chosen_node = get_server_info(returned_choice, option, nodes)
                if not info_about_node_dic:
                    self.d.msgbox("Server is unreachable. Please update server status.")
                    return
                returned_choice = self.print_server_info(info_about_node_dic)
            try:
                server_choices(returned_choice=returned_choice, chosen_node=chosen_node,
                               info_about_node_dic=info_about_node_dic)
            except ConnectionError as err:
                self.d.msgbox("Error while connecting. Please verify your credentials.")
                self._log_message(err)
        else:
            return


if __name__ == "__main__":
    e = Engine()
    e.init_interface()
    exit(0)
