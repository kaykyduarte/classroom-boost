from django.urls import path

from . import views

app_name = "notificacoes"

urlpatterns = [
    path(
        "<int:notificacao_id>/visualizar/",
        views.visualizar_notificacao,
        name="visualizar_notificacao",
    ),
]