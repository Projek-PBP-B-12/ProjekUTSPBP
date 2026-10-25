from django.urls import path

from .views import show_notification


app_name = "notification"

urlpatterns = [
    path("", show_notification, name="show_notification"),
]