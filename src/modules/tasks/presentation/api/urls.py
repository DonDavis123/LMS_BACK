from django.urls import path

from .views.task_detail import TaskDetailView
from .views.task_list import TaskListView


urlpatterns = [
    path("", TaskListView.as_view(), name="tasks"),
    path("<uuid:task_id>/", TaskDetailView.as_view(), name="task-detail"),
]
