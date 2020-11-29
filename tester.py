import enum
import getpass
import json
import os
import platform
from datetime import datetime


class JSONFile():
    def __init__(self, file_path):
        self.file = file_path
        self.data = None
    def __enter__(self):
        with open(self.file, "r") as read_file:
            self.data = json.load(read_file)
            return self
    def __exit__(self, type, value, traceback):
        with open(self.file, "w") as write_file:
            json.dump(self.data, write_file)


class PlbmngJobResult(enum.Enum):
    success = 1
    error = 2
    pending = 3


class PlbmngJobState(enum.Enum):
    scheduled = 1
    running = 2
    stopped = 3


class PlbmngJob():
    def __init__(self, job_id):
        self.job_id = job_id

    def __repr__(self):
        return self.to_json()

    def to_json(self):
        return json.dumps(self, indent=4, default=lambda o: o.__dict__)




class PlbmngJobsFile():
    def __init__(self, file_path):
        self.file_path = file_path

    def read(self):
        with JSONFile(self.file_path) as f:
            return f.data
    
    def add_job(self, job_id, cmd_argv):
        with JSONFile(self.file_path) as f:

            # TODO add check that job does not exist yet, else raise
            job = {
                "job_id": job_id,}
            #     "state": PlbmngJobState.scheduled.value,
            #     "result": PlbmngJobResult.pending.value,
            #     "scheduled_at": datetime.now().isoformat(),
            #     "user": getpass.getuser(),
            #     "user_id": os.geteuid(),
            #     "hostname": platform.node(),
            #     "cmd_argv": cmd_argv,
            # }
            f.data["jobs"].append(job)

    def get_job(self, job_id):
         with JSONFile(self.file_path) as f:
            data = f.data["jobs"]
            job_iterator = filter(lambda jobs_found: jobs_found["job_id"] == job_id, data)
            jobs_found = list(job_iterator)
            if len(jobs_found) > 1:
                raise Exception("More than one item found. Check the DB consistency.")
            if not jobs_found:
                raise Exception(f"No job found with ID: {job_id}")
            return jobs_found[0]

    def del_job(self, job_id):
        job = self.get_job(job_id)
        with JSONFile(self.file_path) as f:
            jobs = f.data["jobs"]            
            jobs.remove(job)
            f.data["jobs"] = jobs
    
    def modify_job(self, attribute, value):
        pass

    def set_job_result(self, job_id, result):
        self.modify_job("foo", "bar")


jobs={'jobs': []}
with open("/tmp/data_file.json", "w") as write_file: 
    json.dump(jobs, write_file)


plbmng_jobs = PlbmngJobsFile('/tmp/data_file.json')
print(plbmng_jobs.read())
plbmng_jobs.add_job(111, "rpm -q kernel")
print(plbmng_jobs.read())
plbmng_jobs.add_job(222, "rpm -q bash")
print(plbmng_jobs.read())
# jobs added
plbmng_jobs.set_job_result(111, PlbmngJobResult.pending)
plbmng_jobs.del_job(111)
plbmng_jobs.del_job(222)
print(plbmng_jobs.read())

