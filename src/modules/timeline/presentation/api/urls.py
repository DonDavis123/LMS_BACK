from django.urls import path

from src.modules.timeline.domain.enums.timeline_entity_type import TimelineEntityType

from .views.timeline import TimelineView


urlpatterns = [
    path(
        "leads/<uuid:entity_id>/",
        TimelineView.as_view(),
        {"entity_type": TimelineEntityType.LEAD.value},
        name="lead-timeline",
    ),
    path(
        "contacts/<uuid:entity_id>/",
        TimelineView.as_view(),
        {"entity_type": TimelineEntityType.CONTACT.value},
        name="contact-timeline",
    ),
    path(
        "accounts/<uuid:entity_id>/",
        TimelineView.as_view(),
        {"entity_type": TimelineEntityType.ACCOUNT.value},
        name="account-timeline",
    ),
    path(
        "tasks/<uuid:entity_id>/",
        TimelineView.as_view(),
        {"entity_type": TimelineEntityType.TASK.value},
        name="task-timeline",
    ),
    path(
        "meetings/<uuid:entity_id>/",
        TimelineView.as_view(),
        {"entity_type": TimelineEntityType.MEETING.value},
        name="meeting-timeline",
    ),
]