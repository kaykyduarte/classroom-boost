from django.urls import path

from .views import enviar_mensagem_view, historico_conversa

app_name = "chat"

urlpatterns = [
    path(
        "conversas/<int:conversa_id>/",
        historico_conversa,
        name="historico_conversa",
    ),
    path(
        "conversas/<int:conversa_id>/mensagens/",
        enviar_mensagem_view,
        name="enviar_mensagem",
    ),
]
