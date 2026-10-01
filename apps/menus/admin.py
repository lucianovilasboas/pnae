from django.contrib import admin

from .models import Menu


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("service_date", "meal_type", "campus", "description")
    list_filter = ("campus", "meal_type", "service_date")
    search_fields = ("description", "notes")
    date_hierarchy = "service_date"
