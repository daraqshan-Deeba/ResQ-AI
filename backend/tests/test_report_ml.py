from app.ml.reports import classify_report, reset_report_model, train_report_model
from app.services.traffic_service import _classify_report_message


def setup_function():
    reset_report_model()


def test_report_model_trains():
    path = train_report_model(force=True)
    assert path.exists()
    reset_report_model()


def test_classify_report_accident():
    train_report_model(force=True)
    reset_report_model()
    assert classify_report("Multi-vehicle collision on highway exit") == "accident"


def test_classify_report_construction():
    train_report_model(force=True)
    reset_report_model()
    assert classify_report("Road under construction near metro") == "construction"


def test_traffic_service_uses_ml_classifier():
    train_report_model(force=True)
    reset_report_model()
    assert _classify_report_message("Gridlock near metro after evening rain") == "congestion"
