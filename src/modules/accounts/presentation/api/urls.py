from django.urls import path

from .views.create_account import CreateAccountView
from .views.get_accounts import GetAccountsView
from .views.get_account_details import GetAccountDetailsView
from .views.update_account import UpdateAccountView
from .views.account_documents import AccountDocumentListView
from .views.account_document_detail import AccountDocumentDetailView
from src.modules.accounts.presentation.api.views.delete_account import (
    DeleteAccountView,
)



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
    path(
        "<uuid:account_id>/update",
        UpdateAccountView.as_view(),
        name="update-account",
    ),
     path(
        "<uuid:account_id>/delete/",
        DeleteAccountView.as_view(),
        name="delete-account",
    ),
    path(
        "<uuid:account_id>/documents/",
        AccountDocumentListView.as_view(),
        name="account-documents",
    ),
    path(
        "<uuid:account_id>/documents/<uuid:document_id>/",
        AccountDocumentDetailView.as_view(),
        name="account-document-detail",
    ),
]
