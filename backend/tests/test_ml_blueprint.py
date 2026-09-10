def test_ml_status_endpoint(client):
    response = client.get("/api/ml/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert "triage_classifier" in payload
    assert "report_classifier" in payload
    assert payload["triage_classifier"]["total_training_rows"] > 0
    assert payload["report_classifier"]["total_training_rows"] > 0
