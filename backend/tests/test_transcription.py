from io import BytesIO
from unittest.mock import AsyncMock, patch

from app.models.schemas import ServiceResult, TranscriptionResult


def test_transcribe_endpoint_success(client):
    with patch(
        "app.services.transcription_service.transcribe_audio_safe",
        new_callable=AsyncMock,
    ) as mock_transcribe:
        mock_transcribe.return_value = ServiceResult(
            available=True,
            data=TranscriptionResult(
                text="My house is flooding",
                language="en",
                model="whisper-large-v3",
            ),
        )

        res = client.post(
            "/api/transcribe",
            data={
                "audio": (BytesIO(b"fake-audio"), "recording.webm"),
                "language": "English",
            },
            content_type="multipart/form-data",
        )

    assert res.status_code == 200
    assert res.get_json()["text"] == "My house is flooding"


def test_transcribe_endpoint_missing_file(client):
    res = client.post("/api/transcribe")
    assert res.status_code == 400
    assert "Missing audio file" in res.get_json()["detail"]


def test_transcribe_endpoint_service_disabled(client):
    with patch(
        "app.services.transcription_service.transcribe_audio_safe",
        new_callable=AsyncMock,
    ) as mock_transcribe:
        mock_transcribe.return_value = ServiceResult(
            available=False,
            error_type="service_disabled",
            detail="Transcription service is not configured.",
        )

        res = client.post(
            "/api/transcribe",
            data={"audio": (BytesIO(b"fake-audio"), "recording.webm")},
            content_type="multipart/form-data",
        )

    assert res.status_code == 503
