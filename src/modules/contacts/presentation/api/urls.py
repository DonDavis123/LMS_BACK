from django.urls import path

from .views.create_contact import CreateContactView
from .views.get_contact_details import GetContactDetailsView

from .views import (
    
    GetContactsView,
)


urlpatterns = [
    path(
        "create/",
        CreateContactView.as_view(),
        name="create-contact",
    ),


    path(
        "",
        GetContactsView.as_view(),
        name="get-contacts",
    ),

      path(
        "<uuid:contact_id>/",
        GetContactDetailsView.as_view(),
        name="get-contact-details",
    ),
]