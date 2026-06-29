"""Shared pytest setup: ensure the SQLite schema exists before any test runs."""
import pytest

from core import database as db


@pytest.fixture(autouse=True, scope="session")
def _init_database():
    db.init_db()
    yield
