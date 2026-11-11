from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from atividades.models import Atividade, Disciplina
from gamificacao.models import Progresso
from notificacoes.models import Notificacao
from notificacoes.services import criar_notificacoes_da_atividade

from .forms import CadastroAlunoForm, DisciplinaForm
from .models import Usuario


def _disciplinas_do_usuario(usuario):
    if usuario.tipo == Usuario.Tipo.ALUNO:
        return Disciplina.objects.filter(
            pk__in=usuario.disciplinas_matriculadas.values("pk"),
        )
    if usuario.tipo == Usuario.Tipo.PROFESSOR or usuario.is_staff:
        return Disciplina.objects.filter(professor=usuario)
    raise PermissionDenied("Seu usuário não possui um perfil de aluno ou professor.")


def inicio(request):
    if request.user.is_authenticated:
        return redirect("usuarios:painel")
    return render(request, "usuarios/inicio.html")


@login_required
def painel(request):
    usuario = request.user
    disciplinas = _disciplinas_do_usuario(usuario)

    if usuario.tipo == Usuario.Tipo.ALUNO:
        atividades = Atividade.objects.filter(disciplina__alunos=usuario)
        notificacoes = Notificacao.objects.filter(
            destinatario=usuario,
            atividade__disciplina__alunos=usuario,
        )
        contexto = {
            "pontos": Progresso.objects.filter(aluno=usuario)
            .values_list("xp_total", flat=True)
            .first() or 0,
        }
        template = "usuarios/painel_aluno.html"
    elif usuario.tipo == Usuario.Tipo.PROFESSOR or usuario.is_staff:
        atividades = Atividade.objects.filter(disciplina__professor=usuario)
        notificacoes = Notificacao.objects.filter(
            destinatario=usuario,
            atividade__disciplina__professor=usuario,
        )
        contexto = {
            "alunos_total": Usuario.objects.filter(
                tipo=Usuario.Tipo.ALUNO,
                disciplinas_matriculadas__professor=usuario,
            ).distinct().count(),
        }
        template = "usuarios/painel_professor.html"
    else:
        raise PermissionDenied("Seu usuário não possui um perfil de aluno ou professor.")

    contexto.update({
        "disciplinas_total": disciplinas.count(),
        "atividades_total": atividades.count(),
        "nao_visualizadas": notificacoes.filter(visualizada=False).count(),
        "disciplinas": disciplinas.select_related("professor")
        .annotate(total_alunos=Count("alunos"))
        .order_by("nome", "pk")[:6],
        "atividades": atividades.select_related("disciplina")
        .order_by("-criada_em", "-pk")[:6],
        "notificacoes": notificacoes.order_by("visualizada", "-criada_em", "-pk")[:6],
    })
    return render(request, template, contexto)


@login_required
def minhas_disciplinas(request):
    disciplinas = (
        _disciplinas_do_usuario(request.user)
        .select_related("professor")
        .annotate(total_alunos=Count("alunos"))
        .order_by("nome", "pk")
    )
    return render(request, "usuarios/disciplinas.html", {"disciplinas": disciplinas})


@login_required
def detalhe_disciplina(request, disciplina_id):
    disciplina = get_object_or_404(
        _disciplinas_do_usuario(request.user)
        .select_related("professor")
        .annotate(total_alunos=Count("alunos")),
        pk=disciplina_id,
    )
    pode_ver_alunos = (
        request.user.tipo != Usuario.Tipo.ALUNO
        and disciplina.professor_id == request.user.pk
    )
    alunos = (
        disciplina.alunos.filter(tipo=Usuario.Tipo.ALUNO)
        .order_by("first_name", "username")
        if pode_ver_alunos else Usuario.objects.none()
    )
    return render(request, "usuarios/detalhe_disciplina.html", {
        "disciplina": disciplina,
        "atividades": disciplina.atividades.order_by("prazo", "pk"),
        "alunos": alunos,
        "pode_ver_alunos": pode_ver_alunos,
    })


@login_required
@require_http_methods(["GET", "POST"])
def criar_disciplina(request):
    if request.user.tipo != Usuario.Tipo.PROFESSOR:
        raise PermissionDenied("Somente professores podem criar disciplinas.")

    form = DisciplinaForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            disciplina = form.save(commit=False)
            disciplina.professor = request.user
            disciplina.save()
            form.save_m2m()
        messages.success(request, "Disciplina criada com sucesso.")
        return redirect("usuarios:detalhe_disciplina", disciplina_id=disciplina.pk)

    return render(request, "usuarios/form_disciplina.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def editar_disciplina(request, disciplina_id):
    if request.user.tipo != Usuario.Tipo.PROFESSOR:
        raise PermissionDenied("Somente professores podem editar disciplinas.")

    disciplinas = Disciplina.objects.filter(professor=request.user)
    if request.method == "POST":
        disciplinas = disciplinas.select_for_update()

    with transaction.atomic():
        disciplina = get_object_or_404(disciplinas, pk=disciplina_id)
        form = DisciplinaForm(
            request.POST if request.method == "POST" else None,
            instance=disciplina,
        )
        if request.method == "POST" and form.is_valid():
            alunos_antes = set(disciplina.alunos.values_list("pk", flat=True))
            disciplina = form.save()
            novos_alunos = list(form.cleaned_data["alunos"].exclude(pk__in=alunos_antes))
            if novos_alunos:
                for atividade in disciplina.atividades.all():
                    criar_notificacoes_da_atividade(atividade, alunos=novos_alunos)
            messages.success(request, "Disciplina e matrículas atualizadas com sucesso.")
            return redirect("usuarios:detalhe_disciplina", disciplina_id=disciplina.pk)

    return render(request, "usuarios/form_disciplina.html", {
        "form": form,
        "disciplina": disciplina,
    })


def cadastro_aluno(request):
    if request.user.is_authenticated:
        return redirect("usuarios:painel")

    if request.method == "POST":
        form = CadastroAlunoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Cadastro realizado! Entre com seu usuário e senha.",
            )
            return redirect("usuarios:login")
    else:
        form = CadastroAlunoForm()

    return render(request, "usuarios/cadastro.html", {"form": form})
