from django.urls import path

from .field_validation import ValidateFieldView

urlpatterns = [
    path(
        "field/",
        ValidateFieldView.as_view(),
        name="validate-field",
    ),
]
