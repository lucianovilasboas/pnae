from django.contrib import admin

from apps.audit.admin_mixin import AuditedAdminMixin

from .models import Campus, ClassGroup


@admin.register(Campus)
class CampusAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "timezone", "active")
    list_filter = ("active",)
    search_fields = ("name", "code")


@admin.register(ClassGroup)
class ClassGroupAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "campus", "course", "academic_year", "active")
    list_filter = ("campus", "academic_year", "active")
    search_fields = ("name", "course")
