from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from notificacoes.services import criar_notificacoes_da_atividade
from usuarios.models import Usuario

from .forms import AtividadeForm
from .models import Atividade


def _atividades_do_usuario(usuario):
    if usuario.tipo == Usuario.Tipo.ALUNO:
        return Atividade.objects.filter(disciplina__alunos=usuario)
    if usuario.tipo == Usuario.Tipo.PROFESSOR or usuario.is_staff:
        return Atividade.objects.filter(disciplina__professor=usuario)
    raise PermissionDenied("Seu usuário não possui um perfil de aluno ou professor.")


@login_required
def lista_atividades(request):
    atividades = (
        _atividades_do_usuario(request.user)
        .select_related("disciplina", "disciplina__professor")
        .order_by("prazo", "pk")
    )
    return render(request, "atividades/lista.html", {"atividades": atividades})


@login_required
def detalhe_atividade(request, atividade_id):
    atividade = get_object_or_404(
        _atividades_do_usuario(request.user)
        .select_related("disciplina", "disciplina__professor"),
        pk=atividade_id,
    )
    return render(request, "atividades/detalhe.html", {"atividade": atividade})


@login_required
@require_http_methods(["GET", "POST"])
def criar_atividade(request):
    if request.user.tipo != Usuario.Tipo.PROFESSOR:
        raise PermissionDenied("Somente professores podem publicar atividades.")

    form = AtividadeForm(
        request.POST if request.method == "POST" else None,
        professor=request.user,
    )
    if request.method == "GET" and request.GET.get("disciplina"):
        try:
            disciplina_id = int(request.GET["disciplina"])
        except ValueError:
            raise Http404("Disciplina não encontrada.") from None
        disciplina = get_object_or_404(
            form.fields["disciplina"].queryset,
            pk=disciplina_id,
        )
        form.initial["disciplina"] = disciplina.pk

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            atividade = form.save()
            criar_notificacoes_da_atividade(atividade)
        messages.success(
            request,
            "Atividade publicada. Os alunos matriculados receberam uma notificação.",
        )
        return redirect("atividades:detalhe", atividade_id=atividade.pk)

    return render(request, "atividades/form_atividade.html", {
        "form": form,
        "tem_disciplinas": form.fields["disciplina"].queryset.exists(),
    })
