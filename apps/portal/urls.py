from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("entrar/", views.login_view, name="login"),
    path("primeiro-acesso/", views.first_access_view, name="first-access"),
    path("recuperar/", views.recover_view, name="recover"),
    path("painel/", views.dashboard, name="dashboard"),
    path("cardapio/", views.week, name="week"),
    path("qr/", views.qr_view, name="qr"),
    path("sair/", views.logout_view, name="logout"),
]
