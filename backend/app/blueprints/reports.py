from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.http_utils import parse_json, validation_error_response
from app.models.schemas import ReportIn
from app.services import database_service, knowledge_service, supabase_storage_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("")
def list_reports():
    return jsonify(database_service.list_reports())


@bp.post("")
def create_report():
    upload = request.files.get("file")
    if upload is not None:
        return _create_report_with_attachment()

    try:
        payload = parse_json(ReportIn, request.get_json())
    except ValidationError as exc:
        return validation_error_response(exc)

    try:
        report = database_service.add_report(
            area=payload.area,
            message=payload.message,
            reporter_name=payload.reporter_name,
        )
    except RuntimeError:
        return jsonify({"detail": "Database service is temporarily unavailable"}), 503

    _index_report_knowledge(report)
    return jsonify(report)


def _create_report_with_attachment():
    area = (request.form.get("area") or "").strip()
    message = (request.form.get("message") or "").strip()
    reporter_name = (request.form.get("reporter_name") or "").strip() or None
    upload = request.files.get("file")

    if not area or not message:
        return jsonify({"detail": "area and message are required"}), 400
    if upload is None or not upload.filename:
        return jsonify({"detail": "file is required for multipart report submission"}), 400

    if not knowledge_service.knowledge_available():
        return jsonify({"detail": "File uploads require Supabase Storage"}), 503

    data = upload.read()
    if not data:
        return jsonify({"detail": "Uploaded file is empty"}), 400

    mime = upload.mimetype or ""
    asset_type = "image" if mime.startswith("image/") else "document"
    extracted = supabase_storage_service.extract_text_content(data, mime, upload.filename)
    content_text = "\n\n".join(part for part in [message, extracted] if part)

    try:
        uploaded = supabase_storage_service.upload_bytes(
            data,
            upload.filename,
            folder="reports",
            content_type=upload.mimetype,
        )
        report = database_service.add_report(
            area=area,
            message=message,
            reporter_name=reporter_name,
            attachment_path=uploaded["storage_path"],
            attachment_url=uploaded["storage_url"],
            attachment_mime=uploaded["mime_type"],
        )
        knowledge_service.ingest_asset(
            title=f"Community report — {area}",
            content_text=content_text,
            asset_type=asset_type,
            area=area,
            storage_path=uploaded["storage_path"],
            storage_url=uploaded["storage_url"],
            mime_type=uploaded["mime_type"],
            source_type="community_report",
            source_id=report["id"],
        )
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400
    except RuntimeError:
        return jsonify({"detail": "Database service is temporarily unavailable"}), 503

    return jsonify(report), 201


def _index_report_knowledge(report: dict) -> None:
    if not knowledge_service.knowledge_available():
        return
    try:
        knowledge_service.ingest_asset(
            title=f"Community report — {report['area']}",
            content_text=report["message"],
            asset_type="report",
            area=report["area"],
            storage_url=report.get("attachment_url"),
            mime_type=report.get("attachment_mime"),
            source_type="community_report",
            source_id=report["id"],
        )
    except Exception:
        pass
