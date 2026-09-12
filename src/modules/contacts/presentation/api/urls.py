from django.urls import path

from .views.create_contact import CreateContactView
from .views.get_contact_details import GetContactDetailsView
from .views.update_contact import UpdateContactView
from .views.delete_contact import DeleteContactView

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

      path(
     "<uuid:contact_id>/update/",
      UpdateContactView.as_view(),
      name="update-contact",
),
      path(
      "<uuid:contact_id>/delete/",
       DeleteContactView.as_view(),
      name="delete-contact",
),
]