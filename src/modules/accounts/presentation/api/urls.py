from django.urls import path

from .views.create_account import CreateAccountView


urlpatterns = [
    path(
        "create/",
        CreateAccountView.as_view(),
        name="create-account",
    ),
]