"""
LLM Scheduler with deadlock prevention.

The locally hosted LLM is a single shared resource: only one inference may run
at a time. Agents, however, are run by a small worker pool and frequently need
*more than one* resource at once (e.g. the ``llm`` lock plus an external API
lock such as ``gmail`` or ``network``). Multiple workers contending for
multiple named resources can deadlock via circular wait.

Two complementary techniques prevent that here:

1. **Canonical lock ordering** — every job acquires all of its resources in a
   single atomic step, always in sorted order. This removes the "hold-and-wait
   in inconsistent order" condition that makes circular wait possible.

2. **Wait–die** — each job carries a monotonically increasing transaction id
   (older = smaller). When a job needs a resource held by another job:
       * if the requester is OLDER, it WAITS;
       * if the requester is YOUNGER, it DIES (aborts and is re-queued).
   Wait–die only ever lets older transactions block, so the wait-for graph can
   never contain a cycle — deadlock is impossible.

The scheduler also consults the ResourceMonitor and *throttles* (defers) jobs
while the machine's CPU/RAM is above the configured limits, and enforces a
watchdog timeout so a wedged inference can't hold the LLM lock forever.
"""
from __future__ import annotations

import itertools
import logging
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, PriorityQueue
from typing import Callable

from config import settings
from core import database as db
from orchestrator.resource_monitor import ResourceMonitor

log = logging.getLogger("scheduler")

_txn_counter = itertools.count(1)


# --------------------------------------------------------------------------- #
# Resource manager (named locks with canonical ordering + wait-die)
# --------------------------------------------------------------------------- #
class ResourceManager:
    """Atomically grants sets of named resources without deadlock."""

    def __init__(self) -> None:
        self._owner: dict[str, tuple[str, int]] = {}  # resource -> (agent, txn_id)
        self._cond = threading.Condition()

    def acquire_all(self, agent: str, txn: int, resources: list[str], timeout: float) -> bool:
        """
        Grant every resource in `resources` atomically. Returns True on success.
        Returns False if the job must DIE (wait-die abort) or times out.
        """
        canonical = sorted(set(resources))
        deadline = time.time() + timeout
        with self._cond:
            while True:
                blockers = [
                    (r, self._owner[r])
                    for r in canonical
                    if r in self._owner and self._owner[r][1] != txn
                ]
                if not blockers:
                    for r in canonical:
                        self._owner[r] = (agent, txn)
                    return True

                # wait-die: a younger requester (larger txn) must die.
                for resource, (holder_agent, holder_txn) in blockers:
                    if txn > holder_txn:
                        db.log_schedule(
                            agent,
                            "deadlock_avoided",
                            f"wait-die: aborted (younger) vs {holder_agent} holding '{resource}'",
                        )
                        return False

                # requester is older than every blocker -> safe to wait.
                remaining = deadline - time.time()
                if remaining <= 0:
                    db.log_schedule(agent, "deadlock_avoided", "wait timeout, abort")
                    return False
                self._cond.wait(timeout=remaining)

    def release_all(self, txn: int) -> None:
        with self._cond:
            for resource in [r for r, (_, t) in self._owner.items() if t == txn]:
                del self._owner[resource]
            self._cond.notify_all()

    def held(self) -> dict[str, str]:
        with self._cond:
            return {r: a for r, (a, _) in self._owner.items()}


# --------------------------------------------------------------------------- #
# Job
# --------------------------------------------------------------------------- #
@dataclass(order=True)
class Job:
    priority: int
    txn: int = field(compare=True)
    agent: str = field(compare=False)
    fn: Callable[[], str] = field(compare=False)
    resources: list[str] = field(compare=False, default_factory=list)
    name: str = field(compare=False, default="")
    attempts: int = field(compare=False, default=0)
    enqueued_at: float = field(compare=False, default=0.0)


# --------------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------------- #
class LLMScheduler:
    """Priority scheduler with a worker pool, throttling and deadlock prevention."""

    def __init__(self, monitor: ResourceMonitor, workers: int = 2) -> None:
        self.monitor = monitor
        self.resources = ResourceManager()
        self._queue: PriorityQueue[Job] = PriorityQueue()
        self._workers = workers
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._active: dict[int, str] = {}  # txn -> agent (currently running)
        self._lock = threading.Lock()
        self.lock_timeout = settings.llm_lock_timeout_seconds
        # Safety net: a job only gives up after waiting this long for its
        # resources (with wait-die it should always succeed well before this).
        self.max_wait_seconds = max(self.lock_timeout, 600)

    # ----- lifecycle ------------------------------------------------------- #
    def start(self) -> None:
        for i in range(self._workers):
            t = threading.Thread(target=self._worker, name=f"sched-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        log.info("Scheduler started with %d workers", self._workers)

    def stop(self) -> None:
        self._stop.set()

    # ----- submission ------------------------------------------------------ #
    def submit(self, agent: str, fn: Callable[[], str], priority: int = 5,
               resources: list[str] | None = None, name: str = "") -> None:
        """
        Queue a unit of work. `priority`: lower = more important.
        `resources`: named locks the job needs (the local LLM is added
        automatically). The orchestrator calls this for every agent run.
        """
        res = list(resources or [])
        if "llm" not in res:
            res.append("llm")
        job = Job(priority=priority, txn=next(_txn_counter), agent=agent,
                  fn=fn, resources=res, name=name or agent,
                  enqueued_at=time.time())
        self._queue.put(job)
        db.log_schedule(agent, "queued", f"priority={priority}, resources={res}")

    # ----- worker loop ----------------------------------------------------- #
    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=1)
            except Empty:
                continue

            # 1) Throttle while the machine is overloaded.
            self._wait_for_capacity(job)

            # 2) Acquire all resources atomically (deadlock-free).
            granted = self.resources.acquire_all(
                job.agent, job.txn, job.resources, timeout=self.lock_timeout
            )
            if not granted:
                self._requeue(job)
                continue

            # 3) Run the job under a watchdog.
            self._run_job(job)

    def _wait_for_capacity(self, job: Job) -> None:
        warned = False
        while not self._stop.is_set():
            overloaded, reason = self.monitor.is_overloaded()
            if not overloaded:
                return
            if not warned:
                db.log_schedule(job.agent, "throttled", reason)
                log.info("Throttling %s: %s", job.agent, reason)
                warned = True
            self._stop.wait(2)

    def _requeue(self, job: Job) -> None:
        # Wait-die: a job that DIED keeps its ORIGINAL transaction id, so it
        # retains its age and is guaranteed to eventually become the oldest
        # waiter (which WAITS rather than dies) and succeed. Giving it a fresh,
        # younger id would make it lose every race and starve.
        job.attempts += 1
        waited = time.time() - job.enqueued_at
        if waited > self.max_wait_seconds:
            db.log_schedule(job.agent, "finished",
                            f"dropped after waiting {int(waited)}s for resources")
            return
        backoff = min(0.25 * job.attempts, 2.0)
        time.sleep(backoff)
        self._queue.put(job)  # same txn preserved

    def _run_job(self, job: Job) -> None:
        with self._lock:
            self._active[job.txn] = job.agent
        db.log_schedule(job.agent, "started", job.name)
        log.info("Running job: %s", job.name)

        result_box: dict[str, str] = {}
        error_box: dict[str, BaseException] = {}

        def _target() -> None:
            try:
                result_box["r"] = job.fn() or ""
            except BaseException as exc:  # noqa: BLE001 - surfaced below
                error_box["e"] = exc

        worker = threading.Thread(target=_target, name=f"job-{job.agent}", daemon=True)
        worker.start()
        worker.join(timeout=self.lock_timeout)

        if worker.is_alive():
            db.log_schedule(job.agent, "finished", "WATCHDOG timeout — lock force-released")
            log.warning("Job %s exceeded watchdog timeout", job.agent)
        elif "e" in error_box:
            db.log_schedule(job.agent, "finished", f"error: {error_box['e']}")
            log.exception("Job %s failed", job.agent, exc_info=error_box["e"])
        else:
            db.log_schedule(job.agent, "finished", result_box.get("r", "")[:120])

        # Always release resources, even on timeout/error.
        self.resources.release_all(job.txn)
        with self._lock:
            self._active.pop(job.txn, None)

    # ----- introspection (dashboard) -------------------------------------- #
    def status(self) -> dict:
        with self._lock:
            active = list(self._active.values())
        return {
            "queued": self._queue.qsize(),
            "active": active,
            "held_resources": self.resources.held(),
            "workers": self._workers,
        }
