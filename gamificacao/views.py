from django.contrib.auth.decorators import login_required
from django.db.models import Value
from django.db.models.functions import Coalesce
from django.shortcuts import render

from usuarios.models import Usuario

from .models import Progresso


@login_required
def ranking(request):
    alunos = (
        Usuario.objects.filter(tipo=Usuario.Tipo.ALUNO, is_active=True)
        .annotate(total_pontos=Coalesce("progresso_gamificacao__xp_total", Value(0)))
        .order_by("-total_pontos", "first_name", "last_name", "username", "pk")[:20]
    )
    meus_pontos = None
    if request.user.tipo == Usuario.Tipo.ALUNO:
        meus_pontos = (
            Progresso.objects.filter(aluno=request.user)
            .values_list("xp_total", flat=True)
            .first() or 0
        )
    return render(request, "gamificacao/ranking.html", {
        "alunos": alunos,
        "meus_pontos": meus_pontos,
    })
