from django.utils import timezone

from .models import Notificacao


def calcular_prioridade(atividade):
    tempo_restante = atividade.prazo - timezone.now()
    horas_restantes = tempo_restante.total_seconds() / 3600

    if horas_restantes <= 24:
        return Notificacao.Prioridade.URGENTE

    if horas_restantes <= 48:
        return Notificacao.Prioridade.IMPORTANTE

    return Notificacao.Prioridade.NORMAL


def criar_notificacoes_da_atividade(atividade):
    prioridade = calcular_prioridade(atividade)

    notificacoes_criadas = []

    for aluno in atividade.disciplina.alunos.all():
        notificacao, criada = Notificacao.objects.get_or_create(
            destinatario=aluno,
            atividade=atividade,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE,
            defaults={
                "titulo": f"Nova atividade: {atividade.titulo}",
                "mensagem": (
                    f"Uma nova atividade foi publicada em "
                    f"{atividade.disciplina.nome}."
                ),
                "prioridade": prioridade,
            },
        )

        notificacoes_criadas.append(
            (notificacao, criada)
        )

    return notificacoes_criadas


def marcar_como_visualizado(notificacao_id, usuario):
    notificacao = Notificacao.objects.get(
        id=notificacao_id,
        destinatario=usuario,
    )

    if not notificacao.visualizada:
        notificacao.visualizada = True
        notificacao.visualizada_em = timezone.now()
        notificacao.save(
            update_fields=["visualizada", "visualizada_em"],
        )
