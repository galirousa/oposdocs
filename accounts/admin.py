from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SiteUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_staff", "is_active", "date_joined")
    readonly_fields = ("external_id",)
    fieldsets = (*UserAdmin.fieldsets, ("Identidad externa", {"fields": ("external_id",)}))
