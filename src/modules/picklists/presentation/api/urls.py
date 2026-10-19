from django.urls import path

from .views.create_option import CreatePicklistOptionView
from .views.delete_option import DeletePicklistOptionView
from .views.get_picklists import GetFieldPicklistView, GetModulePicklistsView
from .views.reorder_options import ReorderPicklistOptionsView
from .views.update_option import UpdatePicklistOptionView

urlpatterns = [
    # Option-level routes first so "options" is never read as a module name.
    path(
        "options/<uuid:option_id>/update/",
        UpdatePicklistOptionView.as_view(),
        name="update-picklist-option",
    ),
    path(
        "options/<uuid:option_id>/delete/",
        DeletePicklistOptionView.as_view(),
        name="delete-picklist-option",
    ),
    path(
        "<str:module>/",
        GetModulePicklistsView.as_view(),
        name="get-module-picklists",
    ),
    path(
        "<str:module>/<str:field>/",
        GetFieldPicklistView.as_view(),
        name="get-field-picklist",
    ),
    path(
        "<str:module>/<str:field>/create/",
        CreatePicklistOptionView.as_view(),
        name="create-picklist-option",
    ),
    path(
        "<str:module>/<str:field>/reorder/",
        ReorderPicklistOptionsView.as_view(),
        name="reorder-picklist-options",
    ),
]
