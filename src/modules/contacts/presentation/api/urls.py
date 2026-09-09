from django.urls import path

from .views.create_contact import CreateContactView


urlpatterns = [
    path(
        "create/",
        CreateContactView.as_view(),
        name="create-contact",
    ),
]