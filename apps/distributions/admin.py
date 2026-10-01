from django.contrib import admin

from .models import Delivery, Distribution


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    list_display = ("service_date", "meal_type", "campus", "status", "estimated_quantity")
    list_filter = ("campus", "status", "meal_type", "service_date")
    search_fields = ("campus__name",)
    date_hierarchy = "service_date"
    readonly_fields = ("opened_at", "closed_at", "created_at", "updated_at")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "delivered_at",
        "distribution",
        "student",
        "delivery_type",
        "status",
        "recorded_by",
    )
    list_filter = ("delivery_type", "status", "distribution__campus")
    search_fields = ("student__full_name", "student__registration_number")
    date_hierarchy = "delivered_at"
    readonly_fields = (
        "delivered_at",
        "reversed_at",
        "reversed_by",
        "reversal_reason",
        "created_at",
    )
