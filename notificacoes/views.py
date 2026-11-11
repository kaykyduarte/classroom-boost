from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from usuarios.models import Usuario

from .models import Notificacao
from .services import marcar_como_visualizado


def _notificacoes_do_usuario(usuario):
    notificacoes = Notificacao.objects.filter(destinatario=usuario)
    if usuario.tipo == Usuario.Tipo.ALUNO:
        return notificacoes.filter(atividade__disciplina__alunos=usuario)
    if usuario.tipo == Usuario.Tipo.PROFESSOR or usuario.is_staff:
        return notificacoes.filter(atividade__disciplina__professor=usuario)
    return notificacoes.none()


@login_required
def lista_notificacoes(request):
    notificacoes = (
        _notificacoes_do_usuario(request.user)
        .select_related("atividade", "atividade__disciplina")
        .order_by("visualizada", "-criada_em", "-pk")
    )
    return render(request, "notificacoes/lista.html", {
        "notificacoes": notificacoes,
        "nao_visualizadas": notificacoes.filter(visualizada=False).count(),
    })


@login_required
@require_POST
def visualizar_notificacao(request, notificacao_id):
    get_object_or_404(_notificacoes_do_usuario(request.user), pk=notificacao_id)
    try:
        marcar_como_visualizado(notificacao_id, request.user)
    except Notificacao.DoesNotExist:
        raise Http404("Notificação não encontrada.") from None

    if request.get_preferred_type(["application/json", "text/html"]) == "text/html":
        messages.success(request, "Notificação marcada como lida.")
        return redirect("notificacoes:lista")

    return JsonResponse({
        "success": True,
        "message": "Notificação visualizada",
    })
