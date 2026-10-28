from django.contrib import admin
from .models import UserProfile
# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "default_location")
    search_fields = ("user__username", "user__email")
    list_select_related = ("user", "default_location")
    autocomplete_fields = ("user",)
