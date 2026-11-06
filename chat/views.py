from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .models import Conversa
from .services import (
    ConversaInvalidaError, 
    MensagemInvalidaError,
    ConteudoMensagemInvalidoError,
    RemetenteNaoAutorizadoError, 
    listar_mensagens, 
    enviar_mensagem,
)

# Create your views here.

@login_required
def historico_conversa(request, conversa_id):
    conversa = get_object_or_404(Conversa, pk=conversa_id)

    try:
        mensagens = listar_mensagens(conversa, request.user)
    except ConversaInvalidaError as exc:
        raise PermissionDenied(
            "Você não tem permissão para visualizar esta conversa."
        ) from exc

    dados = list(
        mensagens.values(
            "id",
            "remetente_id",
            "conteudo",
            "enviada_em"
        )
    )

    return JsonResponse({"mensagens": dados})


@login_required
@require_POST
def enviar_mensagem_view(request, conversa_id):
    conversa = get_object_or_404(Conversa, pk=conversa_id)

    conteudo = request.POST.get("conteudo", "")

    try:
        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=request.user,
            conteudo=conteudo,
        )
    except RemetenteNaoAutorizadoError as exc:
        raise PermissionDenied(
            "Você não tem permissão para enviar mensagens nesta conversa."
        ) from exc
    except ConteudoMensagemInvalidoError:
        return JsonResponse(
            {"erro": "O conteúdo da mensagem não pode estar vazio."},
            status=400,
        )

    return JsonResponse(
        {
            "id": mensagem.pk,
            "remetente_id": mensagem.remetente_id,
            "conteudo": mensagem.conteudo,
            "enviada_em": mensagem.enviada_em,
        },
        status=201,
    )
