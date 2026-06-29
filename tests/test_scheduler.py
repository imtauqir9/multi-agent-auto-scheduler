"""
Unit tests for the deadlock-prevention core (no LLM / network needed).

Run with:  pytest -q
"""
from __future__ import annotations

import threading
import time

from orchestrator.scheduler import ResourceManager


def test_canonical_ordering_grants_disjoint_resources():
    rm = ResourceManager()
    assert rm.acquire_all("A", txn=1, resources=["llm", "gmail"], timeout=2)
    # Disjoint set succeeds concurrently.
    assert rm.acquire_all("B", txn=2, resources=["network"], timeout=2)
    rm.release_all(1)
    rm.release_all(2)
    assert rm.held() == {}


def test_wait_die_younger_aborts():
    rm = ResourceManager()
    # Older transaction (txn=1) holds the llm lock.
    assert rm.acquire_all("Older", txn=1, resources=["llm"], timeout=2)
    # Younger transaction (txn=5) must DIE rather than wait -> returns False fast.
    start = time.time()
    granted = rm.acquire_all("Younger", txn=5, resources=["llm"], timeout=5)
    assert granted is False
    assert time.time() - start < 1.0  # died immediately, did not block
    rm.release_all(1)


def test_wait_die_older_waits_then_acquires():
    rm = ResourceManager()
    assert rm.acquire_all("Holder", txn=10, resources=["llm"], timeout=2)

    result: dict[str, bool] = {}

    def older_request():
        # txn=2 is OLDER than the holder (10) -> it should WAIT, then succeed.
        result["granted"] = rm.acquire_all("OlderWaiter", txn=2, resources=["llm"], timeout=5)

    t = threading.Thread(target=older_request)
    t.start()
    time.sleep(0.3)
    rm.release_all(10)      # release; waiter should now win
    t.join(timeout=3)
    assert result.get("granted") is True


def test_no_deadlock_under_contention():
    """
    Two agents each want {llm, gmail} in opposite mental order. Canonical
    ordering + wait-die must guarantee both eventually complete with no hang.
    """
    rm = ResourceManager()
    done = []

    def agent(name, txn):
        for _ in range(20):
            if rm.acquire_all(name, txn, ["llm", "gmail"], timeout=5):
                time.sleep(0.001)
                rm.release_all(txn)
                break
        done.append(name)

    threads = [
        threading.Thread(target=agent, args=("A", 1)),
        threading.Thread(target=agent, args=("B", 2)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert sorted(done) == ["A", "B"]
    assert rm.held() == {}
