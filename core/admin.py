from django.contrib import admin

from .models import ConsentEvent


@admin.register(ConsentEvent)
class ConsentEventAdmin(admin.ModelAdmin):
    list_display = ("decision", "created_at")
    list_filter = ("decision",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False
