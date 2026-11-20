from django.urls import path

from .views import DailyBriefingView, DashboardStatsView

urlpatterns = [
    path(
        "stats/",
        DashboardStatsView.as_view(),
        name="dashboard-stats",
    ),
    path(
        "briefing/",
        DailyBriefingView.as_view(),
        name="dashboard-briefing",
    ),
]
