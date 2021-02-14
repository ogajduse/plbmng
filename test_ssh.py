import json
import pathlib
import time
import uuid

from plbmng.lib import ssh


EXECUTOR_SCRIPT_PATH = pathlib.Path().absolute().parent.joinpath("executor.py")
TESTING_SCRIPT_PATH = pathlib.Path().absolute().parent.joinpath("testing_script.sh")
HOSTNAME = "localhost"  # ple1.cesnet.cz
USER = "ogajduse"  # cesnetple_vut_utko
KEYFILE = "/home/ogajduse/.ssh/id_rsa"  # students_planetlab

ssh.upload_file(EXECUTOR_SCRIPT_PATH, "/tmp/executor.py", key_filename=KEYFILE, hostname=HOSTNAME, username=USER)
res = ssh.upload_file(TESTING_SCRIPT_PATH, "/tmp/scr.sh", key_filename=KEYFILE, hostname=HOSTNAME, username=USER)

JOB_UUID = str(uuid.uuid4())
RUN_AT = int(time.time()) + 10
EXEC_CMD = f"python3 /tmp/executor.py --run-at {RUN_AT} --run-cmd 'bash /tmp/scr.sh' --job-id {JOB_UUID}"
ssh.command(EXEC_CMD, hostname=HOSTNAME, username=USER, key_filename=KEYFILE, background=True)

running = True
while running:
    ssh.download_file(
        "/home/ogajduse/.plbmng/jobs.json",
        local_file="/tmp/remote_jobs.json",
        hostname=HOSTNAME,
        username=USER,
        key_filename=KEYFILE,
    )
    with open("/tmp/remote_jobs.json", "r") as read_file:
        jobs = json.load(read_file)

    for job in jobs:
        if job["job_id"] == JOB_UUID:
            if job["state"] == "stopped":
                print(f"Job {JOB_UUID} ended.")
                running = False
            if job["state"] == "scheduled":
                print(f"Job {JOB_UUID} is in scheduled state")
                running = True
            if job["state"] == "running":
                print(f"Job {JOB_UUID} is still running")
                running = True

print()
