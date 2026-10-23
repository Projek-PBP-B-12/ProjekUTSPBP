from django.urls import path

from .views import (
    create_shared_post,
    shared_post_list,
    update_shared_post,
    delete_shared_post,
    complete_shared_post,
)

app_name = "sharedpost"

urlpatterns = [
    path("<int:pk>/complete/", complete_shared_post, name="complete"),
    path("<int:pk>/delete/", delete_shared_post, name="delete"),
    path("<int:pk>/edit/", update_shared_post, name="update"),
    path("create/", create_shared_post, name="create"),
    path("", shared_post_list, name="list"),
]
