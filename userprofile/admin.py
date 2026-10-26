from django.contrib import admin
from .models import UserProfile
# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username",)
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
