from django.urls import path

from .views import *

app_name = "FoodItem"

urlpatterns = [
    path("api/get/", get_food_items, name="get_food_items"),
    path("api/delete/<int:fooditem_id>", delete_food_item, name="delete_food_item"),
    path("api/change/<int:fooditem_id>/status/stored", make_food_item_status_stored, name="make_food_item_status_stored"),
    path("api/change/<int:fooditem_id>/status/consumed", make_food_item_status_consumed, name="make_food_item_status_consumed"),
    path("api/change/<int:fooditem_id>/status/offered", make_food_item_status_offered, name="make_food_item_status_offered"),
    path("add/", add_food_item, name="add_food_item"),
    path("change/<int:fooditem_id>", change_food_item, name="change_food_item"),
    path("makananku/", makananku, name="makananku"),
]