from django.urls import path

from . import api

app_name = "distributions_api"

urlpatterns = [
    path("distributions", api.distribution_create, name="create"),
    path("distributions/<int:pk>/open", api.distribution_open, name="open"),
    path("distributions/<int:pk>/close", api.distribution_close, name="close"),
    path("distributions/<int:pk>/scan", api.distribution_scan, name="scan"),
    path("distributions/<int:pk>/extras", api.distribution_extras, name="extras"),
    path("distributions/<int:pk>/summary", api.distribution_summary, name="summary"),
    path("distributions/<int:pk>/pending", api.distribution_pending, name="pending"),
    path("distributions/<int:pk>/report", api.distribution_report, name="report"),
    path("deliveries/<int:pk>/reverse", api.delivery_reverse, name="reverse"),
]
