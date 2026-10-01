from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("name",)
    list_display = ("email", "name", "campus", "role", "is_active", "is_staff")
    list_filter = ("role", "campus", "is_active", "is_staff", "can_authorize_extras")
    search_fields = ("email", "name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados", {"fields": ("name", "campus", "role")}),
        ("Permissões", {"fields": ("can_authorize_extras", "can_reverse_deliveries")}),
        (
            "Acesso",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "campus", "role", "password1", "password2"),
            },
        ),
    )
