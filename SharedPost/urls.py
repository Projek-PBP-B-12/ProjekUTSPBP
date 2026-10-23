from django.urls import path

from .views import create_shared_post, shared_post_list, update_shared_post

app_name = "sharedpost"

urlpatterns = [
    path("<int:pk>/edit/", update_shared_post, name="update"),
    path("create/", create_shared_post, name="create"),
    path("", shared_post_list, name="list"),
]
