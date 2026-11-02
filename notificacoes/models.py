from django.conf import settings
from django.db import models

from atividades.models import Atividade


class Notificacao(models.Model):
    class Prioridade(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        IMPORTANTE = "IMPORTANTE", "Importante"
        URGENTE = "URGENTE", "Urgente"

    class Tipo(models.TextChoices):
        NOVA_ATIVIDADE = "NOVA_ATIVIDADE", "Nova atividade"
        LEMBRETE_PRAZO = "LEMBRETE_PRAZO", "Lembrete de prazo"

    tipo = models.CharField(
    max_length=20,
    choices=Tipo.choices,
    )

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes",
    )

    atividade = models.ForeignKey(
        Atividade,
        on_delete=models.CASCADE,
        related_name="notificacoes",
    )

    titulo = models.CharField(max_length=150)
    mensagem = models.TextField()

    prioridade = models.CharField(
        max_length=10,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
    )

    visualizada = models.BooleanField(default=False)

    criada_em = models.DateTimeField(auto_now_add=True)

    visualizada_em = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.destinatario} - {self.titulo}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["destinatario", "atividade", "tipo"],
                name="unique_notificacao_por_aluno_atividade_tipo",
            )
        ]
