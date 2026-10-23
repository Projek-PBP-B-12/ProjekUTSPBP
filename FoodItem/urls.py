from django.urls import path

from .views import *

app_name = "FoodItem"

urlpatterns = [
    path("api/get/", get_food_items, name="get_food_items"),
    path("api/delete/<int:fooditem_id>", delete_food_item, name="delete_food_item"),
    path("add/", add_food_item, name="add_food_item"),
    path("change/<int:fooditem_id>", change_food_item, name="change_food_item"),
]