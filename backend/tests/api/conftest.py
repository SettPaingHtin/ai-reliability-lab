import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Base


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        api_key=None,
        mock_simulate_latency=False,
        log_level="WARNING",
    )


@pytest.fixture()
def app(settings):
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    return application


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


SAMPLE = "\n".join(
    [
        '{"input": "Capital of France?", "expected": "Paris", "metadata": {"mock_output": "Paris"}}',
        '{"input": "2+2?", "expected": "4", "metadata": {"mock_output": "5"}}',
        '{"input": "Name a color", "rules": [{"type": "contains", "value": "blue", "case_sensitive": false}], "metadata": {"mock_output": "Deep Blue", "mock_report_usage": false}}',
        '{"input": "Always fails", "expected": "x", "metadata": {"mock_error": "error"}}',
    ]
)


def make_dataset(client, text=SAMPLE, project_name="p1"):
    pid = client.post("/api/projects", json={"name": project_name}).json()["id"]
    did = client.post(f"/api/projects/{pid}/datasets", json={"name": "d1"}).json()["id"]
    r = client.post(f"/api/datasets/{did}/import", content=text, headers={"content-type": "text/plain"})
    return pid, did, r
