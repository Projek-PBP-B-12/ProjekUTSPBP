from django.urls import path
from .views import *

app_name = 'Location'

urlpatterns = [
    path('', get_locations, name='get_locations'),
    path('create/', create_location, name='create_location'),
    path('<int:pk>/edit/', update_location, name='update_location'),
    path('<int:pk>/delete/', delete_location, name='delete_location'), 
    path('search/', search_locations, name='search_locations'),
    path('map/', map_page, name='map'),
    path('manage/', manage_locations, name='manage'),
    path('manage/<int:pk>/edit/', manage_edit, name='manage_edit'),
    path('manage/<int:pk>/delete/', manage_delete, name='manage_delete'),
    path('manage/<int:pk>/default/', set_default, name='set_default'),
]
