# tests/test_jobs_api.py

def test_create_job_has_default_state(client):
    # Arrange: prepare payload
    payload = "send welcome email"
    request_body = {
        "payload": payload
    }

    # Act: call API
    response = client.post("/api/jobs", json=request_body)

    # Assert: HTTP layer
    assert response.status_code == 200

    # Assert: JSON layer
    data = response.json()

    assert isinstance(data, dict)

    # Check field availability in the response.
    assert "id" in data
    assert "payload" in data
    assert "status" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "result" in data
    assert "error" in data
    assert "attempts" in data
    assert "max_retries" in data

    # Check field values.
    assert data["payload"] == payload
    assert data["status"] == "queued"
    assert data["result"] is None
    assert data["error"] is None
    assert data["attempts"] == 0
    assert data["max_retries"] == 3

    # Check response field types.
    assert isinstance(data["id"], str)
    assert isinstance(data["payload"], str)
    assert isinstance(data["status"], str)
    assert isinstance(data["created_at"], str)
    assert isinstance(data["updated_at"], str)
    assert isinstance(data["attempts"], int)
    assert isinstance(data["max_retries"], int)

    # Check that required strings are not empty.
    assert data["id"] != ""
    assert data["created_at"] != ""
    assert data["updated_at"] != ""

    # Check that status belongs to the allowed set.
    allowed_statuses = {"queued", "processing", "done", "failed"}
    assert data["status"] in allowed_statuses

    # Attempts cannot be negative.
    assert data["attempts"] >= 0

    # Check that max_retries is in the accepted range.
    assert data["max_retries"] >= 0
    assert data["max_retries"] <= 10

    # The timestamps should match when the job is first created.
    assert data["created_at"] == data["updated_at"]

    # Check that the API can list the newly created job.
    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200

    jobs = list_response.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1

    first_job = jobs[0]
    assert isinstance(first_job, dict)
    assert first_job["id"] == data["id"]
    assert first_job["payload"] == payload
    assert first_job["status"] == "queued"



def test_get_missing_job_returns_404(client):
    response = client.get("/api/jobs/not-a-real-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_delete_processing_job_is_rejected(client):
    create_response = client.post("/api/jobs", json={"payload": "important job"})
    assert create_response.status_code == 200

    job_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/jobs/{job_id}/status",
        json={"status": "processing"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "processing"

    delete_response = client.delete(f"/api/jobs/{job_id}")

    assert delete_response.status_code == 409
    assert delete_response.json()["detail"] == "Cannot delete a processing job"

    get_response = client.get(f"/api/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "processing"


def test_list_jobs_can_filter_by_status(client):
    job_a = client.post("/api/jobs", json={"payload": "queued job"}).json()
    job_b = client.post("/api/jobs", json={"payload": "done job"}).json()

    client.patch(
        f"/api/jobs/{job_b['id']}/status",
        json={"status": "done"},
    )

    response = client.get("/api/jobs", params={"status": "done"})

    assert response.status_code == 200

    jobs = response.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    assert all(job["status"] == "done" for job in jobs)
    assert any(job["id"] == job_b["id"] for job in jobs)
    assert all(job["id"] != job_a["id"] for job in jobs)


def test_requeue_done_job_resets_result_and_error(client):
    create_response = client.post("/api/jobs", json={"payload": "requeue me"})
    job_id = create_response.json()["id"]

    run_response = client.post(f"/api/jobs/{job_id}/run")
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "done"
    assert run_response.json()["result"] is not None

    requeue_response = client.post(f"/api/jobs/{job_id}/requeue")

    assert requeue_response.status_code == 200

    job = requeue_response.json()
    assert job["status"] == "queued"
    assert job["result"] is None
    assert job["error"] is None
