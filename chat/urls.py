from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.caixa_entrada, name="caixa_entrada"),
    path("disciplinas/<int:disciplina_id>/conversa/", views.abrir_conversa, name="abrir_conversa"),
    path("conversas/<int:conversa_id>/tela/", views.detalhe_conversa, name="conversa"),
    path(
        "conversas/<int:conversa_id>/",
        views.historico_conversa,
        name="historico_conversa",
    ),
    path(
        "conversas/<int:conversa_id>/mensagens/",
        views.enviar_mensagem_view,
        name="enviar_mensagem",
    ),
]
