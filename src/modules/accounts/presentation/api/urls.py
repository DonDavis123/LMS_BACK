from django.urls import path

from .views.create_account import CreateAccountView
from .views.get_accounts import GetAccountsView
from .views.get_account_details import GetAccountDetailsView


urlpatterns = [
    path(
        "create/",
        CreateAccountView.as_view(),
        name="create-account",
    ),
      path(
      "",
      GetAccountsView.as_view(),
      name="get-accounts",
    ),

    path(
    "<uuid:account_id>/",
    GetAccountDetailsView.as_view(),
    name="get-account-details",
),
]