from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "api/auth/",
        include("src.modules.authentication.presentation.api.urls"),
    ),

     path(
        "api/",
        include(
            "src.modules.users.presentation.api.urls"
        ),
    ),

    path(
        "api/leads/",
        include("src.modules.leads.presentation.api.urls"),
    ),

    path(
      "api/accounts/",
      include("src.modules.accounts.presentation.api.urls"),
),
    path(
        "api/contacts/",
        include("src.modules.contacts.presentation.api.urls"),
    ),
    path(
        "api/tasks/",
        include("src.modules.tasks.presentation.api.urls"),
    ),
]
