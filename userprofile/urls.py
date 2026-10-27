from django.urls import path

from . import views

app_name = "userprofile"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", views.UserLogoutView.as_view(), name="logout"),
    path("profile/", views.profile_detail, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("contacts/<int:user_id>/", views.donor_contact, name="donor_contact"),
    path("delete/", views.delete_account, name="delete_account"),
]