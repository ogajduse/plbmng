import argparse
import calendar
import sched
import time
from datetime import datetime
from datetime import timedelta


# executor.py --run-at 1606254787 --run-cmd "rpm -qa kernel"

parser = argparse.ArgumentParser(description="Executor script for the remote jobs scheduled by plbmng")
parser.add_argument(
    "--run-at", dest="run_at", required=True, type=int, help="time to run the job at. Requires timestamp (epoch)"
)
parser.add_argument("--run-cmd", dest="run_cmd", required=True, type=str, help="command to run")


def main():
    args = parser.parse_args()
    run_at = args.run_at
    scheduler = sched.scheduler(time.time, time.sleep)
    print("START:", time.time())

    # event x with delay of 1 second
    # enters queue using enterabs method
    scheduler.enterabs(run_at, 1, runner, argument=("Event X",))

    # executing the events
    scheduler.run()


def runner(name):
    print("EVENT:", time.time(), name)


def get_utc_offset():
    ts = time.time()
    return (datetime.fromtimestamp(ts) - datetime.utcfromtimestamp(ts)).total_seconds()


def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def timestr(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f %Z%z")


def timestamp_to_datetime(timestamp_in):
    return datetime.fromtimestamp(timestamp_in)


def get_utc_time(dt):
    return int(time.mktime(dt.timetuple())) + int(time.strftime("%z")) * 6 * 6


def get_utc_timestamp():
    pass


if __name__ == "__main__":
    main()
