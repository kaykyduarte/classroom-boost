from django.urls import path

from . import views

app_name = "gamificacao"

urlpatterns = [
    path("ranking/", views.ranking, name="ranking"),
]
