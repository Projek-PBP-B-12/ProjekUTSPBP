from django.urls import path

from .views import *

app_name = "FoodItem"

urlpatterns = [
    path("api/get/", get_food_items, name="get_food_items"),
    path("api/create/", create_food_item, name="create_food_item"),
]