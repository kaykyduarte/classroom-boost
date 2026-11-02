from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST

from .models import Notificacao
from .services import marcar_como_visualizado


@login_required
@require_POST
def visualizar_notificacao(request, notificacao_id):
    try:
        marcar_como_visualizado(notificacao_id, request.user)
    except Notificacao.DoesNotExist:
        raise Http404("Notificação não encontrada.") from None

    return JsonResponse({
        "success": True,
        "message": "Notificação visualizada",
    })
        
