import os
os.environ["SAFE_ACTION_DB"] = ":memory:"

import pytest
from fastapi.testclient import TestClient
from safe_action_mcp.app import app
from safe_action_mcp.models import AppointmentArgs

@pytest.fixture
def args():
    return AppointmentArgs(provider="Northstar Home Care",service="Heating inspection",date="2026-10-20",time="14:30",quoted_price="89.00",currency="USD",service_location_label="Home")

@pytest.fixture
def client(): return TestClient(app)

@pytest.fixture
def headers(): return {"Origin":"http://127.0.0.1:8765","MCP-Protocol-Version":"2025-11-25"}
