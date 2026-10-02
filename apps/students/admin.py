from django.contrib import admin

from apps.audit.admin_mixin import AuditedAdminMixin

from .models import ImportJob, Student


@admin.register(Student)
class StudentAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("full_name", "registration_number", "campus", "class_group", "active")
    list_filter = ("campus", "class_group", "active")
    search_fields = ("full_name", "registration_number", "email")
    readonly_fields = ("qr_token_hash", "created_at", "updated_at")


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "file_name",
        "campus",
        "status",
        "total_rows",
        "imported_rows",
        "rejected_rows",
        "created_at",
    )
    list_filter = ("campus", "status")
    readonly_fields = ("created_at",)
