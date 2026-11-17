from django.urls import path

from .views.deal_detail import DealDetailView
from .views.deal_list import DealListView
from .views.deal_move_stage import DealMoveStageView


urlpatterns = [
    path("", DealListView.as_view(), name="deals"),
    path("<uuid:deal_id>/", DealDetailView.as_view(), name="deal-detail"),
    path("<uuid:deal_id>/move/", DealMoveStageView.as_view(), name="deal-move-stage"),
]
