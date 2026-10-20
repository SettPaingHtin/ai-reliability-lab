from sqlalchemy import select

from app.models import Result, Run
from app.services.runs import claim_run, execute_run
from tests.api.conftest import SAMPLE, make_dataset


def test_health(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_project_crud_and_conflict(client):
    assert client.post("/api/projects", json={"name": "a"}).status_code == 201
    assert client.post("/api/projects", json={"name": "a"}).status_code == 409
    assert client.post("/api/projects", json={"name": ""}).status_code == 422
    page = client.get("/api/projects?limit=1").json()
    assert page["total"] == 1 and page["limit"] == 1 and len(page["items"]) == 1
    pid = page["items"][0]["id"]
    assert client.get(f"/api/projects/{pid}").status_code == 200
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_import_validation_is_all_or_nothing(client):
    bad = '{"input": "ok", "expected": "x"}\nnot json\n{"input": "y"}'
    _, did, r = make_dataset(client, bad)
    assert r.status_code == 422
    errors = r.json()["detail"]["errors"]
    assert [e["line"] for e in errors] == [2, 3]
    assert client.get(f"/api/datasets/{did}").json()["case_count"] == 0


def test_import_export_round_trip(client):
    _, did, r = make_dataset(client)
    assert r.status_code == 201 and r.json() == {"imported": 4}
    exported = client.get(f"/api/datasets/{did}/export").text
    assert exported.count("\n") == 4 and "Capital of France?" in exported
    cases = client.get(f"/api/datasets/{did}/cases?limit=2&offset=1").json()
    assert cases["total"] == 4 and [c["position"] for c in cases["items"]] == [1, 2]


def test_import_size_limit(client, app):
    app.state.settings.max_import_bytes = 50
    _, _, r = make_dataset(client)
    assert r.status_code == 413


def test_run_end_to_end_with_mock_provider(client):
    pid, did, _ = make_dataset(client)
    started = client.post(f"/api/datasets/{did}/runs", json={"engine": {"max_retries": 0, "backoff_base_s": 0}})
    assert started.status_code == 202
    run = client.get(f"/api/runs/{started.json()['id']}").json()  # TestClient runs background tasks first
    assert run["status"] == "completed" and run["completed"] == 4 and run["total"] == 4
    assert (run["passed"], run["failed"], run["errored"]) == (2, 1, 1)
    assert run["pass_rate"] == 0.5
    assert run["total_tokens"] is not None and run["total_cost_usd"] is not None

    failures = client.get(f"/api/runs/{run['id']}/results?status=failed&status=error").json()
    assert failures["total"] == 2
    failed = next(r for r in failures["items"] if r["status"] == "failed")
    assert failed["input_snapshot"] == "2+2?" and failed["output"] == "5"
    assert failed["score_details"]["kind"] == "deterministic"
    assert failed["score_details"]["rules"][0]["passed"] is False
    errored = next(r for r in failures["items"] if r["status"] == "error")
    assert errored["output"] is None and errored["score"] is None and errored["latency_ms"] is None

    unreported = next(r for r in client.get(f"/api/runs/{run['id']}/results").json()["items"] if r["input_snapshot"] == "Name a color")
    assert unreported["status"] == "passed" and unreported["prompt_tokens"] is None  # unavailable, not zero

    runs = client.get(f"/api/projects/{pid}/runs").json()
    assert runs["total"] == 1


def test_run_rejects_empty_dataset_and_unknown_provider(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    did = client.post(f"/api/projects/{pid}/datasets", json={"name": "d"}).json()["id"]
    assert client.post(f"/api/datasets/{did}/runs", json={}).status_code == 422
    client.post(f"/api/datasets/{did}/import", content='{"input":"a","expected":"b"}', headers={"content-type": "text/plain"})
    assert client.post(f"/api/datasets/{did}/runs", json={"provider": "nope"}).status_code == 422
    assert client.post(f"/api/datasets/{did}/runs", json={"engine": {"concurrency": 1000}}).status_code == 422


def test_duplicate_execution_is_a_noop(client, app):
    _, did, _ = make_dataset(client)
    run_id = client.post(f"/api/datasets/{did}/runs", json={"engine": {"max_retries": 0, "backoff_base_s": 0}}).json()["id"]
    factory, settings = app.state.session_factory, app.state.settings
    execute_run(factory, run_id, settings)  # second submission of an already-finished run
    with factory() as s:
        assert len(list(s.scalars(select(Result).where(Result.run_id == run_id)))) == 4
        assert not claim_run(s, run_id)


def test_resume_skips_cases_that_already_have_results(client, app):
    _, did, _ = make_dataset(client)
    factory, settings = app.state.session_factory, app.state.settings
    run_id = client.post(f"/api/datasets/{did}/runs", json={"engine": {"max_retries": 0, "backoff_base_s": 0}}).json()["id"]
    with factory() as s:  # simulate a crash after partial progress: reopen the run
        s.query(Run).filter(Run.id == run_id).update({"status": "queued"})
        victim = s.scalars(select(Result).where(Result.run_id == run_id).limit(1)).one()
        s.delete(victim)
        s.commit()
    execute_run(factory, run_id, settings)
    with factory() as s:
        assert s.scalar(select(Result.id).where(Result.run_id == run_id).limit(1)) is not None
        assert len(list(s.scalars(select(Result).where(Result.run_id == run_id)))) == 4
        assert s.get(Run, run_id).status == "completed"


def test_deleting_project_cascades(client, app):
    pid, did, _ = make_dataset(client)
    client.post(f"/api/datasets/{did}/runs", json={"engine": {"max_retries": 0, "backoff_base_s": 0}})
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    with app.state.session_factory() as s:
        assert s.scalars(select(Result)).first() is None and s.scalars(select(Run)).first() is None


def test_api_key_auth(app):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    app.state.settings.api_key = SecretStr("s3cret")
    with TestClient(app) as c:
        assert c.get("/api/projects").status_code == 401
        assert c.get("/api/projects", headers={"x-api-key": "wrong"}).status_code == 401
        assert c.get("/api/projects", headers={"x-api-key": "s3cret"}).status_code == 200
        assert c.get("/health/live").status_code == 200  # probes stay open


def test_sample_fixture_is_valid():
    assert SAMPLE.count("\n") == 3
