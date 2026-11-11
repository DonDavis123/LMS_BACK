from django.urls import path

from .views import ResolveMailRecipientsView

urlpatterns = [
    path(
        "recipients/resolve/",
        ResolveMailRecipientsView.as_view(),
        name="mail-resolve-recipients",
    ),
]
