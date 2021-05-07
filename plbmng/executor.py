import argparse
import enum
import getpass
import json
import os
import platform
import sched
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path

HOME_DIR = str(Path.home())
PLBMNG_DIR = HOME_DIR + "/.plbmng"
JOBS_DIR = PLBMNG_DIR + "/jobs"
JOBS_FILE = PLBMNG_DIR + "/jobs.json"


# executor.py --run-at 1606254787 --run-cmd "rpm -qa kernel --job-id b23c4354-9e06-48de-b0a7-996a7e61717d"

parser = argparse.ArgumentParser(description="Executor script for the remote jobs scheduled by plbmng")
parser.add_argument(
    "--run-at", dest="run_at", required=True, type=int, help="time to run the job at. Requires timestamp (epoch)"
)
parser.add_argument("--run-cmd", dest="run_cmd", required=True, type=str, help="command to run")
parser.add_argument("--job-id", dest="job_id", required=True, type=str, help="ID of the job")


def main():
    args = parser.parse_args()
    run_at = args.run_at
    ensure_basic_structure()
    create_job(args.job_id, args.run_cmd, run_at)

    scheduler = sched.scheduler(time.time, time.sleep)
    print("START:", time.time())

    # enters queue using enterabs method
    scheduler.enterabs(
        run_at,
        1,
        runner,
        argument=(
            args.job_id,
            args.run_cmd,
        ),
    )

    # executing the event
    scheduler.run()


def runner(job_id, cmd_argv):
    started_at = datetime.now()
    print("EVENT:", started_at.timestamp(), job_id)
    with PlbmngJobsFile(JOBS_FILE) as jf:
        jf.set_started_at(job_id, started_at)
        jf.set_job_state(job_id, PlbmngJobState.running)

    result, ended_at = run_command(job_id, cmd_argv)

    with PlbmngJobsFile(JOBS_FILE) as jf:
        jf.set_ended_at(job_id, ended_at)
        jf.set_job_state(job_id, PlbmngJobState.stopped)
        jf.set_job_result(job_id, result)


def run_command(job_id, cmd_argv):
    cmd_argv = shlex.split(cmd_argv)
    proc = subprocess.run(cmd_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ended_at = datetime.now()
    create_artefacts(job_id, proc.stdout, proc.stderr)
    if proc.returncode == 0:
        return PlbmngJobResult.success, ended_at
    else:
        return PlbmngJobResult.error, ended_at


def create_artefacts(job_id, stdout, stderr):
    if stdout:
        f_path = JOBS_DIR + "/" + str(job_id) + "/artefacts/stdout"
        with open(f_path, "wb") as write_file:
            write_file.write(stdout)
    if stderr:
        f_path = JOBS_DIR + "/" + str(job_id) + "/artefacts/stderr"
        with open(f_path, "wb") as write_file:
            write_file.write(stderr)


def save_artefacts_file(job_id, out):
    pass


def _ensure_base_dir():
    Path(PLBMNG_DIR).mkdir(exist_ok=True)


def _ensure_jobs_dir():
    _ensure_base_dir()
    Path(JOBS_DIR).mkdir(exist_ok=True)


def _ensure_jobs_json():
    path = Path(JOBS_FILE)
    if not path.exists():
        PlbmngJobsFile(JOBS_FILE, init=True)


def ensure_basic_structure():
    _ensure_jobs_dir()
    _ensure_jobs_json()


def create_job_dir(job_id):
    job_dir = JOBS_DIR + "/" + str(job_id)
    Path(job_dir).mkdir(exist_ok=True)
    Path(job_dir + "/artefacts").mkdir(exist_ok=True)
    return job_dir


def create_job(job_id, cmd_argv, scheduled_at):
    with PlbmngJobsFile(JOBS_FILE) as jf:
        jf.add_job(job_id, cmd_argv, scheduled_at=time_from_timestamp(scheduled_at))
    create_job_dir(job_id)


def get_local_tz_name():
    tzpath = "/etc/localtime"
    zoneinfo_path = "/usr/share/zoneinfo/"
    if os.path.exists(tzpath) and os.path.islink(tzpath):
        tzpath = os.path.realpath(tzpath)
        if zoneinfo_path in tzpath:
            return tzpath.replace(zoneinfo_path, "")


def time_from_iso(dt):
    return datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%f")


def time_to_iso(dt):
    result = dt.isoformat()  # removed timespec="milliseconds" due to the python 3.5 does not support it
    if result.find(".") == -1:
        result += ".000"
    return result


def time_from_timestamp(timestamp_in):
    return datetime.fromtimestamp(timestamp_in)


class PlbmngEnum(enum.Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class PlbmngJobResult(PlbmngEnum):
    success = 1
    error = 2
    pending = 3


class PlbmngJobState(PlbmngEnum):
    scheduled = 1
    running = 2
    stopped = 3


class PlbmngJob:
    def __init__(self, **kwargs):
        mandatory_attr = ["job_id", "cmd_argv"]
        for attr in mandatory_attr:
            if attr not in kwargs:
                raise ValueError("Attribute {} is needed while creating {}".format(attr, self.__class__.__name__))
        default_attr = dict(
            state=PlbmngJobState.scheduled,
            result=PlbmngJobResult.pending,
            scheduled_at=time_to_iso(datetime.now()),
            user=getpass.getuser(),
            user_id=os.geteuid(),
            hostname=platform.node(),
            timezone=get_local_tz_name(),
        )
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

    def __getitem__(cls, o):
        return getattr(cls, o)

    def to_json(self):
        return json.dumps(self, cls=PlbmngJobEncoder)


class PlbmngJobEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, PlbmngJob):
            return o.__dict__
        elif isinstance(o, PlbmngEnum):
            return o.name
        else:
            raise Exception("Object is not of the expected instance")


class PlbmngJobDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        plbmng_job = PlbmngJob(**obj)
        return plbmng_job


class PlbmngJobsFile:
    def __init__(self, file_path, init=False):
        self.file_path = file_path
        self.jobs = []
        self._ensure_file_exists(init)

    def __enter__(self):
        with open(self.file_path, "r") as read_file:
            self.jobs = json.load(read_file, cls=PlbmngJobDecoder)
            return self

    def __exit__(self, type, value, traceback):
        with open(self.file_path, "w") as write_file:
            json.dump(self.jobs, write_file, cls=PlbmngJobEncoder)

    def _ensure_file_exists(self, init):
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
                raise Exception("File {} does not exist.".format(self.file_path))
        else:
            if not is_json():
                raise Exception("File {} is not valid JSON.".format(self.file_path))

    def add_job(self, job_id, cmd_argv, *args, **kwargs):
        if self.get_job(job_id, failsafe=True):
            raise Exception("Job with id {} already exists. There can be only one job with such ID.".format(job_id))
        job = PlbmngJob(job_id=job_id, cmd_argv=cmd_argv, *args, **kwargs)
        self.jobs.append(job)

    def get_job(self, job, failsafe=False):
        if isinstance(job, PlbmngJob):
            job_iterator = filter(lambda job_found: job_found == job, self.jobs)
        else:
            # job is the job_id
            job_iterator = filter(lambda jobs_found: jobs_found["job_id"] == job, self.jobs)
        jobs_found = list(job_iterator)
        if len(jobs_found) > 1:
            raise Exception("More than one item found. Check the DB consistency.")
        if not jobs_found:
            if failsafe:
                return None
            else:
                raise Exception("No job found with ID: {}".format(job))
        return jobs_found[0]

    def get_all_of_attribute(self, attr, val, failsafe=False):
        job_iterator = filter(lambda jobs_found: jobs_found[attr] == val, self.jobs)
        jobs_found = list(job_iterator)
        if not jobs_found:
            if failsafe:
                return None
            else:
                raise Exception("Found no job with {a}: {v}".format(a=attr, v=val))
        return jobs_found

    def del_job(self, job_id):
        job = self.get_job(job_id)
        self.jobs.remove(job)

    def set_job_result(self, job_id, result):
        if not isinstance(result, PlbmngJobResult):
            raise Exception("Type {} expected, got {} instead.".format(PlbmngJobResult, type(result)))
        job = self.get_job(job_id)
        job.result = result

    def set_job_state(self, job_id, state):
        if not isinstance(state, PlbmngJobState):
            raise Exception("Type {} expected, got {} instead.".format(PlbmngJobState, type(state)))
        job = self.get_job(job_id)
        job.state = state

    def set_started_at(self, job_id, started_at):
        if not isinstance(started_at, datetime):
            raise Exception("Type {} expected, got {} instead.".format(datetime, type(started_at)))
        job = self.get_job(job_id)
        job.started_at = time_to_iso(started_at)

    def set_ended_at(self, job_id, ended_at):
        if not isinstance(ended_at, datetime):
            raise Exception("Type {} expected, got {} instead.".format(datetime, type(ended_at)))
        job = self.get_job(job_id)
        job.ended_at = time_to_iso(ended_at)
        self._set_execution_time(job, ended_at)
        self._set_real_time(job, ended_at)

    def _set_execution_time(self, job, ended_at):
        job.execution_time = (ended_at - time_from_iso(job.scheduled_at)).total_seconds()

    def _set_real_time(self, job, ended_at):
        job.real_time = (ended_at - time_from_iso(job.started_at)).total_seconds()


if __name__ == "__main__":
    main()
