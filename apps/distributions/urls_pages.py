from django.urls import path

from . import views

app_name = "distributions"

urlpatterns = [
    path("", views.home, name="home"),
    path("distribuicoes/", views.distribution_list, name="list"),
    path("distribuicoes/<int:pk>/operar/", views.operation, name="operation"),
    path("distribuicoes/<int:pk>/pendentes/", views.pending, name="pending"),
    path("distribuicoes/<int:pk>/entregas/", views.deliveries, name="deliveries"),
    path("distribuicoes/<int:pk>/relatorio/", views.report, name="report"),
    path("distribuicoes/<int:pk>/relatorio.csv", views.report_csv, name="report-csv"),
]
