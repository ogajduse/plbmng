#! /usr/bin/env python3
# Author: Martin Kacmarcik
import locale
import os
import signal
import sys
from datetime import datetime
from itertools import groupby
from pathlib import Path

import pysftp
from dialog import Dialog
from gevent import joinall
from paramiko.ssh_exception import SSHException
from pssh.clients.native.parallel import ParallelSSHClient

from plbmng.executor import PlbmngJob
from plbmng.executor import PlbmngJobResult
from plbmng.executor import PlbmngJobState
from plbmng.executor import time_from_iso
from plbmng.executor import time_from_timestamp
from plbmng.lib.database import PlbmngDb
from plbmng.lib.library import clear
from plbmng.lib.library import copy_files
from plbmng.lib.library import delete_jobs
from plbmng.lib.library import get_all_jobs
from plbmng.lib.library import get_all_nodes
from plbmng.lib.library import get_last_server_access
from plbmng.lib.library import get_non_stopped_jobs
from plbmng.lib.library import get_remote_jobs
from plbmng.lib.library import get_server_info
from plbmng.lib.library import get_stopped_jobs
from plbmng.lib.library import jobs_downloaded_artefacts
from plbmng.lib.library import NeedToFillPasswdFirstInfo
from plbmng.lib.library import OPTION_DNS
from plbmng.lib.library import OPTION_GCC
from plbmng.lib.library import OPTION_IP
from plbmng.lib.library import OPTION_KERNEL
from plbmng.lib.library import OPTION_MEM
from plbmng.lib.library import OPTION_PYTHON
from plbmng.lib.library import plot_servers_on_map
from plbmng.lib.library import run_remote_command
from plbmng.lib.library import schedule_remote_command
from plbmng.lib.library import search_by_location
from plbmng.lib.library import search_by_regex
from plbmng.lib.library import search_by_sware_hware
from plbmng.lib.library import server_choices
from plbmng.lib.library import update_availability_database_parent
from plbmng.lib.library import verify_api_credentials_exist
from plbmng.lib.library import verify_ssh_credentials_exist
from plbmng.utils.config import first_run
from plbmng.utils.config import get_db_path
from plbmng.utils.config import get_plbmng_user_dir
from plbmng.utils.config import get_remote_jobs_path
from plbmng.utils.config import settings
from plbmng.utils.logger import init_logger
from plbmng.utils.logger import logger

# from dynaconf import settings

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))


class Engine:
    """
    Class used for the interaction with the user and decision making based on user's input.
    """

    # _conf_path = "/conf/plbmng.conf"
    user_nodes = "/database/user_servers.node"
    path = ""
    _debug = False
    _filtering_options = None

    def __init__(self):
        from plbmng import __version__

        self.version = __version__

        init_logger()
        self.d = Dialog(dialog="dialog", autowidgetsize=True)
        try:  # check whether it is first run
            settings.first_run
            PlbmngDb.init_db_schema()
        except AttributeError:
            pass
        self.db = PlbmngDb()
        locale.setlocale(locale.LC_ALL, "")
        self.d.set_background_title("Planetlab Server Manager " + __version__)
        self.path = get_plbmng_user_dir()

        logger.info("Plbmng engine initialized. Version: {}", __version__)

    def init_interface(self) -> None:
        """
        Main function of Engine class. Will show root page of plbmng.
        """

        def signal_handler(sig, frame):
            clear()
            logger.info("Terminating program. You have pressed Ctrl+C")
            exit(1)

        signal.signal(signal.SIGINT, signal_handler)

        try:  # check whether it is first run
            settings.first_run
            first_run()
            self.first_run_message()
        except AttributeError:
            pass

        while True:
            # Main menu
            code, tag = self.d.menu(
                "Choose one of the following options:",
                choices=[
                    ("1", "Access servers"),
                    ("2", "Monitor servers"),
                    ("3", "Plot servers on map"),
                    ("4", "Run jobs on servers"),
                    ("5", "Extras"),
                ],
                title="MAIN MENU",
            )

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
                elif tag == "4":
                    self.run_jobs_on_servers_menu()
                elif tag == "5":
                    self.extras_menu()
            else:
                clear()
                exit(0)

    def run_jobs_on_servers_menu(self):
        while True:
            code, tag = self.d.menu(
                "Choose one of the following options:",
                choices=[
                    ("1", "Copy files to server(s)"),
                    ("2", "Run one-off remote command"),
                    ("3", "Schedule remote job"),
                    ("4", "Display jobs state"),
                    ("5", "Refresh jobs state"),
                    ("6", "Job artefacts"),
                    ("7", "Clean up jobs"),
                ],
                title="Remote execution menu",
            )
            if code == self.d.OK:
                if tag == "1":
                    self.copy_file()
                elif tag == "2":
                    self.run_remote_command()
                elif tag == "3":
                    self.schedule_remote_cmd()
                elif tag == "4":
                    self.display_jobs_state_menu()
                elif tag == "5":
                    self.refresh_jobs_status()
                elif tag == "6":
                    self.job_artefacts_menu()
                elif tag == "7":
                    self.job_cleanup_menu()
            else:
                return

    def extras_menu(self):
        """
        Extras menu
        """
        code, tag = self.d.menu(
            "Choose one of the following options:",
            choices=[
                ("1", "Add server to database"),
                ("2", "Statistics"),
                ("3", "About"),
            ],
            title="EXTRAS",
        )
        if code == self.d.OK:
            if tag == "1":
                self.add_external_server_menu()
            elif tag == "2":
                self.stats_gui(self.db.get_stats())
            elif tag == "3":
                self.about_gui(self.version)

    def filtering_options_gui(self) -> int:
        """
        Filtering options menu.

        :return: Code based on PING AND SSH values.
        :rtype: int
        """
        active_filters = self.db.get_filters_for_access_servers(binary_out=True)
        code, t = self.d.checklist(
            "Press SPACE key to choose filtering options",
            height=0,
            width=0,
            list_height=0,
            choices=[
                ("1", "Search for SSH accessible machines", active_filters["ssh"]),
                ("2", "Search for PING accessible machines", active_filters["ping"]),
            ],
        )

        if code == self.d.OK:
            self.db.set_filtering_options(t)
            if len(t) == 2:
                return 3
            elif "1" in t:
                return 1
            elif "2" in t:
                return 2
        # No filters applied
        return None

    def stats_gui(self, stats_dic: dict) -> None:
        """
        Stats menu.

        :param stats_dic: Dictionary which contains number of servers in database,\
        number of servers which responded to the ping or ssh check.
        :type stats_dic: dict
        """
        self.d.msgbox(
            """
        Servers in database: """
            + str(stats_dic["all"])
            + """
        SSH available: """
            + str(stats_dic["ssh"])
            + """
        Ping available: """
            + str(stats_dic["ping"])
            + """
        """,
            width=0,
            height=0,
            title="Current statistics since the last servers status update:",
        )

    def about_gui(self, version):
        """
        About menu.

        :param version: Current version of plbmng.
        :type version: str
        """
        self.d.msgbox(
            """
                PlanetLab Server Manager
                Project supervisor:
                    Dan Komosny
                Authors:
                    Tomas Andrasov
                    Filip Suba
                    Martin Kacmarcik
                    Ondrej Gajdusek

                Version """
            + version
            + """
                This application is licensed under MIT license.
                """,
            title="About",
        )

    def plot_servers_on_map_gui(self):
        """
        Plot servers on map menu.
        """
        while True:
            code, tag = self.d.menu(
                "Choose one of the following options:",
                choices=[
                    ("1", "Plot servers responding to ping"),
                    ("2", "Plot SSH available servers"),
                    ("3", "Plot all servers"),
                ],
                title="Map menu",
            )
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
                "Please use 'Set credentials' option in main menu to set them."
            )
        while True:
            code, tag = self.d.menu(
                "Choose one of the following options:",
                # ("1", "Set crontab for status update"),
                choices=[("1", "Update server list"), ("2", "Update server status")],
                title="Monitoring menu",
                height=0,
                width=0,
            )
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
                                "Please use 'Set credentials' option in main menu to set them."
                            )
                    else:
                        continue
                elif tag == "2":
                    if self.d.yesno("This can take few minutes. Do you want to continue?") == self.d.OK:
                        if not verify_ssh_credentials_exist():
                            self.d.msgbox(
                                "Error! Your ssh credentials are not set. "
                                "Please use 'Set credentials' option in main menu to set them."
                            )
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

    def pick_date(self):
        text = "Select date you want to run the job at."
        code, date = self.d.calendar(text=text)
        if code == self.d.OK:
            code, time = self.d.timebox(text)
            if code == self.d.OK:
                if date and time:
                    return datetime.strptime(
                        f"{date[0]:0>2}, {date[1]:0>2}, {date[2]:0>2}, {time[0]:0>2}, {time[1]:0>2}, {time[2]:0>2}",
                        "%d, %m, %Y, %H, %M, %S",
                    )
                else:
                    return None
        if code == self.d.CANCEL:
            return None

    def run_remote_command(self):
        text = "Type in the remote command"
        init = ""
        code, remote_cmd = self.d.inputbox(text=text, init=init, height=0, width=0)
        if code == self.d.OK:
            servers = self.access_servers_gui(checklist=True)
        else:
            return
        if not servers:
            self.d.msgbox("You did not select any servers!")
            return

        ret = run_remote_command(self.d, remote_cmd, servers)

        if ret:
            self.d.msgbox("Command was run successfully!")
            return
        self.d.msgbox("There was an error running the command.")
        # TODO: Print more meaningful message to the user, containing the error.
        return

    def schedule_remote_cmd(self):
        text = "Type in the remote command"
        init = ""
        date = self.pick_date()
        if not date:
            self.d.msgbox("Wrong date input!")
            return
        code, remote_cmd = self.d.inputbox(text=text, init=init, height=0, width=0)
        if code == self.d.OK:
            if not remote_cmd:
                self.d.msgbox("No remote command entered. Please provide a command to run on the remote host.")
                return
            servers = self.access_servers_gui(checklist=True)
        else:
            return
        if not servers:
            self.d.msgbox("You did not select any servers!")
            return
        schedule_remote_command(remote_cmd, date, servers, self.db)
        self.d.msgbox("Command scheduled successfully.")

    def job_info_s(self, job):
        return f"""Scheduled at:  {time_from_timestamp(int(float(job.scheduled_at)))}
Node hostname: {job.hostname}
Command:       {job.cmd_argv}
State:         {job.state.name}
Result:        {'No result yet' if not job.result else PlbmngJobResult(job.result).name}
Started at     {'Not yet started' if not job.started_at else time_from_timestamp(float(job.started_at))}
Ended at       {'Not yet ended' if not job.ended_at else time_from_timestamp(float(job.ended_at))}
ID:            {job.job_id}"""

    def display_job_state(self, jobs, job_id: str):
        job = list(filter(lambda jobs_found: jobs_found.job_id == job_id, jobs))[0]
        text = self.job_info_s(job)
        self.d.scrollbox(text)

    def display_jobs_state_menu(self):
        while True:
            code, tag = self.d.menu(
                "Choose one of the following options:",
                choices=[
                    ("1", "Display non-finished jobs state"),
                    ("2", "Display finished jobs state"),
                ],
                title="Display jobs state menu",
            )
            if code == self.d.OK:
                if tag == "1":
                    self.display_non_finished_jobs()
                elif tag == "2":
                    self.display_finished_jobs()
            else:
                return

    def display_non_finished_jobs(self):
        jobs: list(PlbmngJob) = get_non_stopped_jobs(self.db)
        self.host_jobs_menu(jobs, "non-finished")

    def display_finished_jobs(self):
        jobs: list(PlbmngJob) = get_stopped_jobs(self.db)
        self.host_jobs_menu(jobs, "finished")

    def host_jobs_menu(self, jobs, state):
        def key_func(k):
            return k.hostname

        host_choices = []
        hosts = list(dict(groupby(jobs, key_func)).keys())
        if len(hosts) > 0:
            for i, host in enumerate(hosts, start=1):
                host_choices.append((str(i), host))
            while True:
                text = f"Hosts with {state} jobs:"
                code, tag = self.d.menu(text, choices=host_choices)
                if code == self.d.OK:
                    selected_host = hosts[int(tag) - 1]
                    choices = []
                    for job in filter(lambda x: x.hostname == selected_host, jobs):
                        choices.append((job.job_id, job.cmd_argv))
                    while True:
                        text = f"{state.capitalize()} jobs on {selected_host}"
                        code, tag = self.d.menu(text, choices=choices)
                        if code == self.d.OK:
                            self.display_job_state(jobs, tag)
                        else:
                            break
                else:
                    return
        else:
            self.d.msgbox(f"No {state} jobs to display.")

    def refresh_jobs_status(self):
        def key_func(k):
            return k.hostname

        ns_jobs = get_non_stopped_jobs(self.db)
        if len(ns_jobs) < 1:
            self.d.msgbox("There are no non-stopped jobs to update.")
            return
        hosts = list(dict(groupby(ns_jobs, key_func)).keys())
        ssh_key = settings.remote_execution.ssh_key
        user = settings.planetlab.slice
        client = ParallelSSHClient(hosts, user=user, pkey=ssh_key)
        cmds = client.copy_remote_file(f"/home/{user}/.plbmng/jobs.json", f"{get_remote_jobs_path()}/jobs.json")
        joinall(cmds, raise_error=True)

        fetched_jobs = []
        for host in hosts:
            # get jobs for the current host
            fetched_jobs.extend(get_remote_jobs(host))
        jobs_intersection = set(fetched_jobs).intersection(set(ns_jobs))
        # jobs_to_ignore = set(fetched_jobs).difference(set(ns_jobs))
        # jobs_to_delete_from_local_db = set(ns_jobs).difference(set(fetched_jobs))
        # update database
        for job in jobs_intersection:
            job = next((fjob for fjob in fetched_jobs if fjob == job), None)
            self.db.update_job(
                job.job_id,
                job.state.value,
                job.result.value,
                time_from_iso(job.started_at).timestamp(),
                time_from_iso(job.ended_at).timestamp(),
            )
        self.d.msgbox("Jobs updated successfully.")

    def job_artefacts_menu(self):
        while True:
            code, tag = self.d.menu(
                "Choose one of the following options:",
                choices=[
                    ("1", "Show job artefacts"),
                    ("2", "Download job artefacts"),
                ],
                title="Job artefacts menu",
            )
            if code == self.d.OK:
                if tag == "1":
                    self.show_job_artefacts_menu()
                elif tag == "2":
                    self.download_job_artefacts()
            else:
                return

    def download_job_artefacts(self):
        def key_func(k):
            return k.hostname

        jobs = get_stopped_jobs(self.db)
        # make difference between jobs that already have artefacts downloaded
        jobs_interested = set(jobs).difference(set(jobs_downloaded_artefacts(jobs)))
        if not jobs_interested:
            self.d.msgbox("No job artefacts to update.")
            return
        hosts = list(dict(groupby(jobs_interested, key_func)).keys())

        ssh_key = settings.remote_execution.ssh_key
        user = settings.planetlab.slice
        unsuccessfull_hosts = []
        successfull_hosts = []
        for host in hosts:
            local_dir = f"{get_remote_jobs_path()}/{host}"
            Path(local_dir).mkdir(exist_ok=True)
            try:
                # TODO: Use pssh instead of pysftp
                with pysftp.Connection(host, username=user, private_key=ssh_key) as sftp:
                    with sftp.cd(f"/home/{user}/.plbmng/jobs"):
                        sftp.get_r(".", local_dir)
                        successfull_hosts.append(host)
            except SSHException:
                unsuccessfull_hosts.append(host)

        if len(unsuccessfull_hosts) > 0:
            text = (
                "The job artefacts from the following hosts were not downloaded:\n"
                + "\n".join(unsuccessfull_hosts)
                + "\n\nMake sure that these hosts were added to the 'known_hosts' file."
            )
            self.d.msgbox(text)

        if len(successfull_hosts) > 0:
            text = f"Job artefacts from {len(successfull_hosts)} host{'s' if len(successfull_hosts) > 1 else '' } \
                downloaded successfully."
        else:
            text = "No job artefacts were downloaded."
        self.d.msgbox(text)

    def show_job_artefacts_menu(self):
        def key_func(k):
            return k.hostname

        jobs = get_stopped_jobs(self.db)
        jobs_art_down = jobs_downloaded_artefacts(jobs)

        hosts = list(dict(groupby(jobs_art_down, key_func)).keys())
        host_choices = []
        if len(hosts) > 0:
            for i, host in enumerate(hosts, start=1):
                host_choices.append((str(i), host))
            while True:
                text = f"Hosts with downloaded artefacts:"
                code, tag = self.d.menu(text, choices=host_choices)
                if code == self.d.OK:
                    selected_host = hosts[int(tag) - 1]
                    choices = []
                    for job in filter(lambda x: x.hostname == selected_host, jobs_art_down):
                        choices.append((job.job_id, job.cmd_argv))
                    while True:
                        text = f"Job artefacts jobs from {selected_host}"
                        code, tag = self.d.menu(text, choices=choices)
                        if code == self.d.OK:
                            self.server_job_artefacts_menu(jobs, tag)
                        else:
                            break
                else:
                    return
        else:
            self.d.msgbox(f"There are no job artefacts downloaded. Nothing to show.")

    def server_job_artefacts_menu(self, jobs, job_id):
        job = list(filter(lambda jobs_found: jobs_found.job_id == job_id, jobs))[0]
        path = f"{get_remote_jobs_path()}/{job.hostname}/{job.job_id}/artefacts/"
        p = Path(path).glob("**/*")
        files = [x for x in p if x.is_file()]
        artefact_choices = []
        if files:
            for i, file in enumerate(files, start=1):
                artefact_choices.append((str(i), file.name))
            while True:
                text = f"Artefacts for job {job_id}:"
                code, tag = self.d.menu(text, choices=artefact_choices)
                if code == self.d.OK:
                    selected_file = files[int(tag) - 1]
                    self.d.textbox(selected_file.as_posix())
                else:
                    break

    def job_cleanup_menu(self):
        state_filter = {k: False for k in PlbmngJobState.list()}
        server_filter = []
        while True:
            code, tag = self.d.menu(
                "Choose one of the following options of filtering jobs:",
                choices=[("1", "State"), ("2", "Servers"), ("3", "Preview jobs to cleanup")],
                title="Jobs cleanup menu",
            )
            if code == self.d.OK:
                if tag == "1":
                    state_filter = self.job_state_choice_menu(state_filter)
                elif tag == "2":
                    server_filter = self.hosts_cleanup_filter_menu(server_filter)
                elif tag == "3":
                    self.preview_job_cleanup(state_filter, server_filter)
            else:
                return

    def job_state_choice_menu(self, state_filter):
        choices = []
        for state, v in state_filter.items():
            choices.append((str(state), PlbmngJobState(state).name.capitalize(), v))
        code, tag = self.d.checklist(
            "Press SPACE key to choose filtering options",
            choices=choices,
        )
        return {s: (True if str(s) in tag else False) for s in state_filter}

    def hosts_cleanup_filter_menu(self, server_filter):
        def key_func(k):
            return k.hostname

        jobs: list(PlbmngJob) = get_all_jobs(self.db)
        hosts = list(dict(groupby(jobs, key_func)).keys())
        if len(hosts) > 0:
            host_choices = [(str(i), host, host in server_filter) for i, host in enumerate(hosts, start=1)]
            while True:
                text = f"Choose hosts to filter:"
                code, tag = self.d.checklist(text, choices=host_choices)
                return [host for host in hosts if host in [hosts[int(t) - 1] for t in tag]]
        else:
            text = "There are no hosts to filter by. This indicates that you have no jobs in database."
            self.d.msgbox(text)

    def preview_job_cleanup(self, state_filter, server_filter):
        invalid_state_f = all(s is False for s in state_filter.values())
        invalid_server_f = server_filter is None or len(server_filter) < 1
        text = ""
        if invalid_state_f:
            text += "No state was chosen. Please choose at least one state to filter by."
        if invalid_server_f:
            if invalid_state_f:
                text += "\n\n"
            text += "No server was chosen. Please choose at least one server to filter by."
        if invalid_state_f or invalid_server_f:
            self.d.msgbox(text=text)
            return
        state_filter = [PlbmngJobState(s) for s in state_filter if state_filter[s]]
        jobs: list(PlbmngJob) = get_all_jobs(self.db)
        filtered_jobs = filter(lambda job: (job.state in state_filter and job.hostname in server_filter), jobs)
        filtered_jobs = sorted(filtered_jobs, key=lambda job: job.hostname)
        hosts = groupby(filtered_jobs, lambda job: job.hostname)
        if not filtered_jobs:
            self.d.msgbox("No jobs found for the criteria set.")
            return
        text = ""
        for host, h_jobs in hosts:
            text += host + "\n"
            for job in h_jobs:
                jobtext = self.job_info_s(job)
                text += "\t\t" + "\t\t".join(jobtext.splitlines(True)) + "\n\n"
            text += "\n\n"
        tag = self.d.scrollbox(text, extra_button=True, extra_label="Clean jobs")
        if tag == self.d.OK:
            pass
        elif tag == self.d.EXTRA:
            text = f"Do you want to clean {len(filtered_jobs)} jobs?"  # TODO treat singular here
            tag = self.d.yesno(text=text)
            if tag == self.d.CANCEL:
                self.d.msgbox("No jobs were cleaned up.")
                return
            elif tag == self.d.OK:
                delete_jobs(self.db, filtered_jobs)
                self.d.msgbox(f"{len(filtered_jobs)} jobs were cleaned up.")

    def copy_file(self):
        """
        Copy files to servers menu.
        """
        text = "Type in destination path on the target hosts. Path to specific file must be specified!"
        init = "/home/" + settings.planetlab.slice
        code, source_path = self.d.fselect(filepath="/home/", height=40, width=60)

        if code == self.d.OK:
            servers = self.access_servers_gui(checklist=True)
        else:
            return
        if not servers:
            self.d.msgbox("You did not select any servers!")
            return
        code, destination_path = self.d.inputbox(text=text, init=init, height=0, width=0)
        if code == self.d.OK:
            ret = copy_files(dialog=self.d, source_path=source_path, hosts=servers, destination_path=destination_path)
        else:
            return
        if ret:
            self.d.msgbox("Copy successful!")
            return
        self.d.msgbox("Could not copy file to the all servers!")
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
            menu_text = (
                """
            \nActive filters: """
                + filter_options
            )

            code, tag = self.d.menu(
                "Choose one of the following options:" + menu_text,
                choices=[
                    ("1", "Access last server"),
                    ("2", "Filtering options"),
                    ("3", "Search by DNS"),
                    ("4", "Search by IP"),
                    ("5", "Search by location"),
                    ("6", "Search by SW/HW"),
                ],
                title="ACCESS SERVERS",
            )
            if code == self.d.OK:
                # Filtering options
                nodes = self.db.get_nodes(path=self.path, choose_availability_option=self._filtering_options)
                # Access last server
                if tag == "1":
                    if checklist:
                        return self.last_server_menu(True)
                    else:
                        self.last_server_menu(checklist)
                elif tag == "2":
                    self._filtering_options = self.filtering_options_gui()
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
        if not verify_ssh_credentials_exist():
            prepared_choices = [
                ("1", "Connect via SSH (Credentials not set!)"),
                ("2", "Connect via MC (Credentials not set!)"),
                ("3", "Show on map"),
            ]
        else:
            prepared_choices = [("1", "Connect via SSH"), ("2", "Connect via MC"), ("3", "Show on map")]
        code, tag = self.d.menu(info_about_node_dic["text"], height=0, width=0, menu_height=0, choices=prepared_choices)
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
                code, tag = self.d.menu("These are the results:", choices=prepared_choices, title="Search results")
            else:
                code, tag = self.d.checklist("These are the results:", choices=prepared_choices, title="Search results")
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
            "Please navigate to ~/.plbmng directory and set the credentials in the settings file.",
            height=0,
            width=0,
        )

    def need_to_fill_passwd_first_info(self):
        """
        Need to fill in password first menu.
        """
        self.d.msgbox("Credentials are not set. Please go to menu and set them now")

    def add_external_server_menu(self):
        """
        Add external server into the plbmng database(NOT TO THE PLANETLAB NETWORK!).
        """
        code, text = self.d.editbox(get_db_path("user_nodes"), height=0, width=0)
        if code == self.d.OK:
            with open(self.path + self.user_nodes, "w") as nodeFile:
                nodeFile.write(text)

    def last_server_menu(self, no_menu) -> None:
        """
        Return last accessed server menu.
        """
        info_about_node_dic = None
        chosen_node = None
        try:
            info_about_node_dic, chosen_node = get_last_server_access(self.path)
        except FileNotFoundError:
            self.d.msgbox("You did not access any server yet.")
            return
        if no_menu:
            return [chosen_node["dns"]]
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
        code, tag = self.d.menu(
            "Filter by software/hardware:",
            choices=[
                ("1", "gcc version"),  # - %s" % stats["gcc"]
                ("2", "python version"),  # - %s" % stats["python"]
                ("3", "kernel version"),  # - %s" % stats["kernel"]
                ("4", "total memory"),  # - %s" % stats["memory"]
            ],
        )
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
                logger.error(err)
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
            logger.error(err)

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
                server_choices(
                    returned_choice=returned_choice, chosen_node=chosen_node, info_about_node_dic=info_about_node_dic
                )
            except ConnectionError as err:
                self.d.msgbox("Error while connecting. Please verify your credentials.")
                logger.error(err)
        else:
            return


if __name__ == "__main__":
    e = Engine()
    e.init_interface()
    exit(0)
