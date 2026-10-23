from django.urls import path

from .views import create_shared_post, shared_post_list

app_name = "sharedpost"

urlpatterns = [
    path("create/", create_shared_post, name="create"),
    path("", shared_post_list, name="list"),
]