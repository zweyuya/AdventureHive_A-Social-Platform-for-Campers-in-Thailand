"""Reuse the shared test fixtures, so the evidence runs on exactly the same setup as tests/."""
from tests.conftest import (  # noqa: F401
    _clear_throttle_cache, api_client, location, login, make_trip, make_user, user,
)

import logging

import pytest


@pytest.fixture(autouse=True)
def _quiet_request_log():
    """Django logs every 401/403 as a warning; hide it so the printed tables stay clean."""
    log = logging.getLogger("django.request")
    old = log.level
    log.setLevel(logging.ERROR)
    yield
    log.setLevel(old)
