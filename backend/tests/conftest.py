"""Dependências auxiliares exclusivas da suíte de testes."""

from __future__ import annotations

import sys
import types


try:
    import apscheduler  # noqa: F401
except ModuleNotFoundError:
    apscheduler_module = types.ModuleType("apscheduler")
    schedulers_module = types.ModuleType("apscheduler.schedulers")
    background_module = types.ModuleType("apscheduler.schedulers.background")
    base_module = types.ModuleType("apscheduler.schedulers.base")

    class BackgroundScheduler:
        def __init__(self, *args, **kwargs):
            self.running = False
            self.state = 0
            self._jobs = {}

        def add_job(self, func, **kwargs):
            job = types.SimpleNamespace(id=kwargs.get("id"))
            self._jobs[job.id] = job
            return job

        def start(self):
            self.running = True
            self.state = 1

        def shutdown(self, wait=False):
            self.running = False
            self.state = 0

        def get_jobs(self):
            return list(self._jobs.values())

        def get_job(self, job_id):
            return self._jobs.get(job_id)

        def remove_job(self, job_id):
            self._jobs.pop(job_id, None)

    background_module.BackgroundScheduler = BackgroundScheduler
    base_module.STATE_STOPPED = 0

    sys.modules["apscheduler"] = apscheduler_module
    sys.modules["apscheduler.schedulers"] = schedulers_module
    sys.modules["apscheduler.schedulers.background"] = background_module
    sys.modules["apscheduler.schedulers.base"] = base_module
