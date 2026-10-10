from django.urls import path

from . import views

app_name = "campus"

urlpatterns = [
    path("", views.campus_select, name="select"),
]
