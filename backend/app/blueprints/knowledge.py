from flask import Blueprint, jsonify, request

from app.services import knowledge_service

bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")


@bp.get("/search")
def search_knowledge():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"detail": "Query parameter 'q' is required"}), 400

    area = (request.args.get("area") or "").strip() or None
    try:
        limit = min(int(request.args.get("limit", 5)), 20)
    except ValueError:
        return jsonify({"detail": "Invalid limit"}), 400

    if not knowledge_service.knowledge_available():
        return jsonify({"detail": "Knowledge search requires Supabase"}), 503

    results = knowledge_service.search_knowledge(query, limit=limit, area=area)
    return jsonify(
        {
            "query": query,
            "area": area,
            "results": results,
            "vector_search": len(results) > 0,
        }
    )


@bp.post("/upload")
def upload_knowledge():
    if not knowledge_service.knowledge_available():
        return jsonify({"detail": "Knowledge upload requires Supabase"}), 503

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    area = (request.form.get("area") or "").strip() or None
    asset_type = (request.form.get("asset_type") or "document").strip()

    if not title:
        return jsonify({"detail": "title is required"}), 400
    if not description:
        return jsonify({"detail": "description is required"}), 400

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"detail": "file is required"}), 400

    data = upload.read()
    if not data:
        return jsonify({"detail": "Uploaded file is empty"}), 400

    try:
        asset = knowledge_service.upload_and_ingest(
            data,
            upload.filename,
            title=title,
            description=description,
            area=area,
            asset_type=asset_type,
            content_type=upload.mimetype,
            source_type="manual_upload",
        )
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400
    except RuntimeError:
        return jsonify({"detail": "Storage service is temporarily unavailable"}), 503

    return jsonify(asset), 201
