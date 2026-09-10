from flask import Blueprint, jsonify

from app.services import database_service

bp = Blueprint("shelters", __name__, url_prefix="/api/shelters")


@bp.get("")
def list_shelters():
    return jsonify(database_service.list_shelters())
