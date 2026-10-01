from django.urls import path

from . import views

app_name = "distributions"

urlpatterns = [
    path("", views.home, name="home"),
    path("distribuicoes/", views.distribution_list, name="list"),
    path("distribuicoes/<int:pk>/operar/", views.operation, name="operation"),
    path("distribuicoes/<int:pk>/pendentes/", views.pending, name="pending"),
]
