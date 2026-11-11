from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from atividades.models import Disciplina
from usuarios.models import Usuario

from .models import Conversa
from .services import (
    ConversaInvalidaError, 
    ConteudoMensagemInvalidoError,
    RemetenteNaoAutorizadoError, 
    criar_ou_obter_conversa,
    listar_mensagens, 
    enviar_mensagem,
)

def _renderizar_conversa(request, conversa, *, conteudo="", erro=None, status=200):
    try:
        historico = listar_mensagens(conversa, request.user).select_related("remetente")
    except ConversaInvalidaError as exc:
        raise PermissionDenied("Você não tem permissão para visualizar esta conversa.") from exc

    eh_aluno = conversa.aluno_id == request.user.pk
    return render(request, "chat/conversa.html", {
        "conversa": conversa,
        "historico": historico,
        "outro_participante": conversa.professor if eh_aluno else conversa.aluno,
        "eh_aluno": eh_aluno,
        "conteudo": conteudo,
        "erro": erro,
    }, status=status)


@login_required
@require_GET
def caixa_entrada(request):
    usuario = request.user
    conversas = (
        Conversa.objects.filter(Q(aluno=usuario) | Q(professor=usuario))
        .select_related("aluno", "professor", "disciplina")
        .annotate(
            ultima_atividade=Coalesce(Max("mensagens__enviada_em"), "criada_em"),
            total_mensagens=Count("mensagens"),
        )
        .order_by("-ultima_atividade", "-pk")
    )
    if usuario.tipo == Usuario.Tipo.ALUNO:
        disciplinas = Disciplina.objects.filter(
            pk__in=usuario.disciplinas_matriculadas.values("pk"),
        )
    elif usuario.tipo == Usuario.Tipo.PROFESSOR:
        disciplinas = Disciplina.objects.filter(professor=usuario)
    else:
        disciplinas = Disciplina.objects.none()

    return render(request, "chat/caixa_entrada.html", {
        "conversas": conversas,
        "disciplinas": disciplinas.select_related("professor")
        .annotate(total_alunos=Count("alunos")).order_by("nome", "pk"),
    })


@login_required
@require_POST
def abrir_conversa(request, disciplina_id):
    disciplina = get_object_or_404(Disciplina.objects.select_related("professor"), pk=disciplina_id)
    if request.user.tipo == Usuario.Tipo.ALUNO:
        aluno = request.user
        professor = disciplina.professor
    elif request.user.tipo == Usuario.Tipo.PROFESSOR:
        if disciplina.professor_id != request.user.pk:
            raise PermissionDenied("Somente o professor responsável pode abrir esta conversa.")
        try:
            aluno_id = int(request.POST.get("aluno_id", ""))
        except (ValueError, TypeError):
            raise Http404("Aluno não encontrado.") from None
        aluno = get_object_or_404(
            disciplina.alunos.filter(tipo=Usuario.Tipo.ALUNO), pk=aluno_id,
        )
        professor = request.user
    else:
        raise PermissionDenied("Somente alunos e professores podem iniciar conversas.")

    try:
        conversa = criar_ou_obter_conversa(aluno, professor, disciplina)
    except ConversaInvalidaError as exc:
        raise PermissionDenied("Você não pode iniciar esta conversa nesta disciplina.") from exc
    return redirect("chat:conversa", conversa_id=conversa.pk)


@login_required
@require_GET
def detalhe_conversa(request, conversa_id):
    conversa = get_object_or_404(
        Conversa.objects.select_related("aluno", "professor", "disciplina"), pk=conversa_id,
    )
    return _renderizar_conversa(request, conversa)


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
    except ConteudoMensagemInvalidoError as exc:
        if request.get_preferred_type(["application/json", "text/html"]) == "text/html":
            return _renderizar_conversa(
                request, conversa, conteudo=conteudo, erro=str(exc), status=400,
            )
        return JsonResponse(
            {"erro": "O conteúdo da mensagem não pode estar vazio."},
            status=400,
        )

    if request.get_preferred_type(["application/json", "text/html"]) == "text/html":
        return redirect("chat:conversa", conversa_id=conversa.pk)

    return JsonResponse(
        {
            "id": mensagem.pk,
            "remetente_id": mensagem.remetente_id,
            "conteudo": mensagem.conteudo,
            "enviada_em": mensagem.enviada_em,
        },
        status=201,
    )
