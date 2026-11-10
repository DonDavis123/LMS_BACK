from django.apps import AppConfig


class CalendarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.modules.calendar"
    # "calendar" would clash with the standard-library module name as an
    # app label only if it were imported bare; the label stays explicit.
    label = "lms_calendar"
