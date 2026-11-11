from django.urls import path

from . import views

app_name = "notificacoes"

urlpatterns = [
    path("", views.lista_notificacoes, name="lista"),
    path(
        "<int:notificacao_id>/visualizar/",
        views.visualizar_notificacao,
        name="visualizar_notificacao",
    ),
]
