from django.urls import path

from . import views

app_name = "distributions"

urlpatterns = [
    path("", views.home, name="home"),
]
