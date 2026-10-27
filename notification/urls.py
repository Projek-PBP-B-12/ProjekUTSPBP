from django.urls import path

from .views import show_notification, mark_notification_read


app_name = "notification"

urlpatterns = [
    path("", show_notification, name="show_notification"),
    path("<int:pk>/read/", mark_notification_read,name="mark_read",),
]