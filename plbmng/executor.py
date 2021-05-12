import argparse
import enum
import getpass
import json
import logging
import os
import platform
import sched
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List
from typing import Tuple
from typing import Union

HOME_DIR = str(Path.home())
PLBMNG_DIR = HOME_DIR + "/.plbmng"
JOBS_DIR = PLBMNG_DIR + "/jobs"
JOBS_FILE = PLBMNG_DIR + "/jobs.json"


# executor.py --run-at 1606254787 --run-cmd "date -d now" --job-id b23c4354-9e06-48de-b0a7-996a7e61717d

parser = argparse.ArgumentParser(description="Executor script for the remote jobs scheduled by plbmng")
parser.add_argument(
    "--run-at", dest="run_at", required=True, type=int, help="time to run the job at. Requires timestamp (epoch)"
)
parser.add_argument("--run-cmd", dest="run_cmd", required=True, type=str, help="command to run")
parser.add_argument("--job-id", dest="job_id", required=True, type=str, help="ID of the job")


def main() -> None:
    """
    Execute runner and schedule tasks.

    Run when the module itself is executed.
    """
    logging.basicConfig(level=logging.INFO)  # TODO: create logfile and returnit as artefact
    args = parser.parse_args()
    run_at = args.run_at
    ensure_basic_structure()
    create_job(args.job_id, args.run_cmd, run_at)

    scheduler = sched.scheduler(time.time, time.sleep)
    logging.info("START: " + str(time.time()))

    # enters queue using enterabs method
    scheduler.enterabs(run_at, 1, runner, argument=(args.job_id, args.run_cmd))

    # executing the event
    scheduler.run()


def runner(job_id: str, cmd_argv: str) -> None:
    """
    Runner for executing :py:class:`PlbmngJob`.

    :param job_id: ID of the job to create and execute.
    :param cmd_argv: Command to run.
    """
    started_at = datetime.now()
    logging.info("EVENT: " + str(started_at.timestamp()) + job_id)
    with PlbmngJobsFile(JOBS_FILE) as jf:
        jf._set_started_at(job_id, started_at)
        jf._set_job_state(job_id, PlbmngJobState.running)

    result, ended_at = run_command(job_id, cmd_argv)

    with PlbmngJobsFile(JOBS_FILE) as jf:
        jf._set_ended_at(job_id, ended_at)
        jf._set_job_state(job_id, PlbmngJobState.stopped)
        jf._set_job_result(job_id, result)


def run_command(job_id: str, cmd_argv: str) -> Tuple["PlbmngEnum", datetime]:
    """
    Run command as a subprocess and create its artefacts.

    :param job_id: ID of the job to create artefacts for.
    :param cmd_argv: Command to run.
    :return: Job result and the ``ended_at`` time.
    """
    cmd_argv = shlex.split(cmd_argv)
    proc = subprocess.run(cmd_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ended_at = datetime.now()
    create_artefacts(job_id, proc.stdout, proc.stderr)
    if proc.returncode == 0:
        return PlbmngJobResult.success, ended_at
    else:
        return PlbmngJobResult.error, ended_at


def create_artefacts(job_id: str, stdout: bytes, stderr: bytes) -> None:
    """
    Create artefacts for the given job.

    Currently supports only stdout and stderr.

    :param job_id: ID of the job.
    :param stdout: STDOUT returned by :py:mod:`subprocess <subprocess>`
    :param stderr: STDERR returned by :py:mod:`subprocess <subprocess>`
    """
    if stdout:
        _save_artefacts_file(job_id, "stdout", stdout)
    if stderr:
        _save_artefacts_file(job_id, "stderr", stderr)


def _save_artefacts_file(job_id: str, out_type: str, out: bytes) -> None:
    f_path = JOBS_DIR + "/" + str(job_id) + "/artefacts/" + out_type
    with open(f_path, "wb") as write_file:
        write_file.write(out)


def _ensure_base_dir() -> None:
    Path(PLBMNG_DIR).mkdir(exist_ok=True)


def _ensure_jobs_dir() -> None:
    _ensure_base_dir()
    Path(JOBS_DIR).mkdir(exist_ok=True)


def _ensure_jobs_json() -> None:
    path = Path(JOBS_FILE)
    if not path.exists():
        PlbmngJobsFile(JOBS_FILE, init=True)


def ensure_basic_structure() -> None:
    """Ensure that *jobs* dir and the *jobs.json* file exist."""
    _ensure_jobs_dir()
    _ensure_jobs_json()


def create_job_dir(job_id: str) -> str:
    """
    Create job directory.

    :param job_id: ID of the job to create job directory for.
    :return: Path to the job directory.
    """
    job_dir = JOBS_DIR + "/" + str(job_id)
    Path(job_dir).mkdir(exist_ok=True)
    Path(job_dir + "/artefacts").mkdir(exist_ok=True)
    return job_dir


def create_job(job_id: str, cmd_argv: str, scheduled_at: int) -> None:
    """
    Create job and create artefacts for it.

    :param job_id: ID of the job.
    :param cmd_argv: Command for the given job.
    :param scheduled_at: Time at which the time was scheduled. Represented as timestamp.
    """
    with PlbmngJobsFile(JOBS_FILE) as jf:
        jf.add_job(job_id, cmd_argv, scheduled_at=time_from_timestamp(scheduled_at))
    create_job_dir(job_id)


def get_local_tz_name() -> str:
    """
    Return local timezone.

    :return: Local timezone.
    """
    tzpath = "/etc/localtime"
    zoneinfo_path = "/usr/share/zoneinfo/"
    if os.path.exists(tzpath) and os.path.islink(tzpath):
        tzpath = os.path.realpath(tzpath)
        if zoneinfo_path in tzpath:
            return tzpath.replace(zoneinfo_path, "")


def time_from_iso(dt: str) -> datetime:
    """
    Convert ISO 8601 time to :py:class:`datetime <datetime.datetime>` object.

    :param dt: Text string containing ISO 8601 formatted time.
    :return: :py:class:`datetime <datetime.datetime>` object as a time representation.
    """
    return datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%f")


def time_to_iso(dt: datetime) -> str:
    """
    Convert :py:class:`datetime <datetime.datetime>` object to ISO 8601 style formatted time.

    :param dt: :py:class:`datetime <datetime.datetime>` object as a time representation.
    :return: Text string containing ISO 8601 formatted time.
    """
    result = dt.isoformat()  # removed timespec="milliseconds" due to the python 3.5 does not support it
    if result.find(".") == -1:
        result += ".000"
    return result


def time_from_timestamp(timestamp_in: Union[int, float]) -> datetime:
    """
    Convert timestamp to :py:class:`datetime <datetime.datetime>` object.

    :param timestamp_in: Number representing the epoch.
    :return: :py:class:`datetime <datetime.datetime>` object as a time representation.
    """
    return datetime.fromtimestamp(timestamp_in)


class PlbmngEnum(enum.Enum):
    """Abstraction for all enumerators related to plbmng jobs."""

    @classmethod
    def list(cls) -> list:  # noqa: A003
        """
        List all values of the :py:class:`PlbmngEnum`.

        :return: List of all possible values for the given :py:class:`PlbmngEnum`.
        """
        return list(map(lambda c: c.value, cls))


class PlbmngJobResult(PlbmngEnum):
    """Job result enumerator."""

    success = 1
    error = 2
    pending = 3


class PlbmngJobState(PlbmngEnum):
    """Job state enumerator."""

    scheduled = 1
    running = 2
    stopped = 3


class PlbmngExecutorException(Exception):
    """Abstraction for all plbmng executor exceptions."""

    pass


class ValidationError(PlbmngExecutorException):
    """
    Exception for operations causing database inconsistency.

    Exception raised in case of operation causing inconsistency of the database
    or if the database is in inconsistent state.
    """

    pass


class JobNotFound(PlbmngExecutorException):
    """Exception raised when the job is not found in the *jobs.json* file."""

    pass


class PlbmngJob:
    """Representation of remote job used within the plbmng."""

    def __init__(self, **kwargs) -> None:
        """
        Collect all ``kwargs`` and create an object for :py:class:`PlbmngJob`.

        :param **kwargs: Arguments for the plbmng job.
        :raises ValueError: If any of the required arguments is missing.
        """
        mandatory_attr = ["job_id", "cmd_argv"]
        for attr in mandatory_attr:
            if attr not in kwargs:
                raise ValueError("Attribute {} is needed while creating {}".format(attr, self.__class__.__name__))
        default_attr = {
            "state": PlbmngJobState.scheduled,
            "result": PlbmngJobResult.pending,
            "scheduled_at": time_to_iso(datetime.now()),
            "user": getpass.getuser(),
            "user_id": os.geteuid(),
            "hostname": platform.node(),
            "timezone": get_local_tz_name(),
        }
        # define allowed attributes with no default value
        more_allowed_attr = ["job_id", "cmd_argv", "started_at", "ended_at", "execution_time", "real_time"]
        allowed_attr = list(default_attr.keys()) + more_allowed_attr
        default_attr.update(kwargs)
        self.__dict__.update((k, v) for k, v in default_attr.items() if k in allowed_attr)
        # deal with PlbmngEnums
        for attr in ["state", "result"]:
            enm = getattr(self, attr)
            if not isinstance(enm, PlbmngEnum):
                e_class = eval("PlbmngJob" + attr.capitalize())
                try:
                    setattr(self, attr, e_class[enm])
                except KeyError:
                    setattr(self, attr, e_class(enm))
        if isinstance(self.scheduled_at, datetime):
            self.scheduled_at = time_to_iso(self.scheduled_at)

    def __repr__(self):
        return self.to_json()

    def __hash__(self):
        return hash(self.job_id)

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.job_id == other.job_id

    def __getitem__(self, o):
        return getattr(self, o)

    def to_json(self) -> str:
        """
        Dump the plbmng job to JSON using :py:class:`PlbmngJobEncoder`.

        :return: plbmng job encoded in JSON string.
        """
        return json.dumps(self, cls=_PlbmngJobEncoder)


class _PlbmngJobEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, PlbmngJob):
            return o.__dict__
        elif isinstance(o, PlbmngEnum):
            return o.name
        else:
            raise TypeError("Object is not of the expected instance")


class _PlbmngJobDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs) -> None:
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj) -> PlbmngJob:
        plbmng_job = PlbmngJob(**obj)
        return plbmng_job


class PlbmngJobsFile:
    """Context manager for the *jobs.json* file containing one or more :py:class:`PlbmngJob`-s."""

    def __init__(self, file_path: str, init: bool = False) -> None:
        """
        Create context for the *jobs.json* file located in ``file_path``.

        The job file is created if ``init`` is set to :py:obj:`True`.

        :param file_path: Path to the *jobs.json* file.
        :param init: Create the jobs file if :py:obj:`True`, defaults to :py:obj:`False`.
        """
        self.file_path = file_path
        self.jobs = []
        self._ensure_file_exists(init)

    def __enter__(self):
        with open(self.file_path, "r") as read_file:
            self.jobs = json.load(read_file, cls=_PlbmngJobDecoder)
            return self

    def __exit__(self, exc_type, exc_value, exc_traceback):  # noqa: U100
        with open(self.file_path, "w") as write_file:
            json.dump(self.jobs, write_file, cls=_PlbmngJobEncoder)

    def _ensure_file_exists(self, init) -> None:
        def is_json():
            with open(self.file_path, "r") as read_file:
                try:
                    json.load(read_file)
                except ValueError:
                    return False
                return True

        self.file_path = os.path.abspath(self.file_path)
        if not os.path.exists(self.file_path):
            if init:
                with open(self.file_path, "w") as write_file:
                    json.dump([], write_file)
            else:
                raise FileNotFoundError("File {} does not exist.".format(self.file_path))
        else:
            if not is_json():
                raise ValueError("File {} is not valid JSON.".format(self.file_path))

    def add_job(self, job_id: str, cmd_argv: str, *args: str, **kwargs: int) -> None:
        """
        Add job to the *jobs.json* file.

        .. # noqa: DAR101

        :param job_id: Job ID to be added.
        :param cmd_argv: Command associated with the job.

        :raises ValidationError: If job with ``job_id`` already exists.
        """
        if self.get_job(job_id, failsafe=True):
            raise ValidationError(
                "Job with id {} already exists. There can be only one job with such ID.".format(job_id)
            )
        job = PlbmngJob(job_id=job_id, cmd_argv=cmd_argv, *args, **kwargs)
        self.jobs.append(job)

    def get_job(self, job: Union[PlbmngJob, str], failsafe: bool = False) -> Union[PlbmngJob, None]:
        """
        Get job from the *jobs.json* file.

        This method is failsafe based on the ``failsafe`` argument.

        :param job: plbmng job to be looked-up
        :param failsafe: If :py:obj:`True` no exception will be raised and , defaults to :py:obj:`False`.
        :raises ValidationError: Is raised if DB inconsistency is detected.
        :raises JobNotFound: is raised if the job is not found and the method is not ``failsafe``.
        :return: Job found | None if no job found
        """
        if isinstance(job, PlbmngJob):
            job_iterator = filter(lambda job_found: job_found == job, self.jobs)
        else:
            # job is the job_id
            job_iterator = filter(lambda jobs_found: jobs_found["job_id"] == job, self.jobs)
        jobs_found = list(job_iterator)
        if len(jobs_found) > 1:
            raise ValidationError("More than one item found. Check the DB consistency.")
        if not jobs_found:
            if failsafe:
                return None
            else:
                raise JobNotFound("No job found with ID: {}".format(job))
        return jobs_found[0]

    def get_all_of_attribute(self, attr: str, val: object, failsafe=False) -> List[PlbmngJob]:
        """
        Get all jobs whose ``attr` is equal to ``val``.

        :param attr: Attribute name to be looked for in :py:class:`PlbmngJob`.
        :param val: Attribute value.
        :param failsafe: Optional argument, method will not raise
            exceptions if set to :py:obj:`True`, defaults to :py:obj:`False`.
        :raises JobNotFound: If no jobs are found.
        :return: List of jobs that have ``attr`` == ``val``.
        """
        job_iterator = filter(lambda jobs_found: jobs_found[attr] == val, self.jobs)
        jobs_found = list(job_iterator)
        if not jobs_found:
            if failsafe:
                return None
            else:
                raise JobNotFound("Found no job with {a}: {v}".format(a=attr, v=val))
        return jobs_found

    def del_job(self, job_id: str) -> None:
        """
        Delete job.

        :param job_id: ID of the job to be deleted.
        """
        job = self.get_job(job_id)
        self.jobs.remove(job)

    def _set_job_result(self, job_id, result) -> None:
        if not isinstance(result, PlbmngJobResult):
            raise TypeError("Type {} expected, got {} instead.".format(PlbmngJobResult, type(result)))
        job = self.get_job(job_id)
        job.result = result

    def _set_job_state(self, job_id, state) -> None:
        if not isinstance(state, PlbmngJobState):
            raise TypeError("Type {} expected, got {} instead.".format(PlbmngJobState, type(state)))
        job = self.get_job(job_id)
        job.state = state

    def _set_started_at(self, job_id, started_at) -> None:
        if not isinstance(started_at, datetime):
            raise TypeError("Type {} expected, got {} instead.".format(datetime, type(started_at)))
        job = self.get_job(job_id)
        job.started_at = time_to_iso(started_at)

    def _set_ended_at(self, job_id, ended_at) -> None:
        if not isinstance(ended_at, datetime):
            raise TypeError("Type {} expected, got {} instead.".format(datetime, type(ended_at)))
        job = self.get_job(job_id)
        job.ended_at = time_to_iso(ended_at)
        self._set_execution_time(job, ended_at)
        self._set_real_time(job, ended_at)

    def _set_execution_time(self, job, ended_at) -> None:
        job.execution_time = (ended_at - time_from_iso(job.scheduled_at)).total_seconds()

    def _set_real_time(self, job, ended_at) -> None:
        job.real_time = (ended_at - time_from_iso(job.started_at)).total_seconds()


if __name__ == "__main__":
    main()
