"""ResQ AI context models for Redis Context Retriever / Context Surfaces."""

from context_surfaces.context_model import ContextField, ContextModel


class CommunityReport(ContextModel):
    """Ground-truth community incident report."""

    __redis_key_template__ = "report:{id}"

    id: str = ContextField(description="Report ID", is_key_component=True)
    area: str = ContextField(description="Neighborhood or locality", index="text")
    message: str = ContextField(description="Situation description", index="text")
    verified: bool = ContextField(description="Whether the report is verified", index="tag")
    created_at: str = ContextField(description="ISO timestamp", index="text", sortable=True)


class Shelter(ContextModel):
    """Emergency shelter with manually maintained occupancy."""

    __redis_key_template__ = "shelter:{id}"

    id: str = ContextField(description="Shelter ID", is_key_component=True)
    name: str = ContextField(description="Shelter name", index="text")
    capacity: int = ContextField(description="Maximum capacity", index="numeric", sortable=True)
    occupied: int = ContextField(description="Current occupancy", index="numeric", sortable=True)
    address: str = ContextField(description="Street address", index="text")


class SosEvent(ContextModel):
    """Persisted SOS event with notification delivery status."""

    __redis_key_template__ = "sos:{event_id}"

    event_id: str = ContextField(description="SOS event ID", is_key_component=True)
    latitude: float = ContextField(description="Latitude", index="numeric", sortable=True)
    longitude: float = ContextField(description="Longitude", index="numeric", sortable=True)
    situation: str = ContextField(description="Optional situation text", index="text")
    notification_status: str = ContextField(
        description="FCM delivery status",
        index="tag",
        allowed_values=[
            "pending_notification",
            "notification_accepted",
            "notification_failed",
            "notification_disabled",
        ],
    )
    created_at: str = ContextField(description="ISO timestamp", index="text", sortable=True)
