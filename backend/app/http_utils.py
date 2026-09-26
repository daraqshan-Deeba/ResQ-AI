from __future__ import annotations

from typing import Any, TypeVar

from flask import jsonify
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def parse_json(model: type[T], payload: Any) -> T:
    return model.model_validate(payload or {})


def validation_error_response(exc: ValidationError):
    safe = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return jsonify({"detail": safe}), 422
