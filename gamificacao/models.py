from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Progresso(models.Model):
    """Resumo do progresso do aluno."""

    aluno = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="progresso_gamificacao",
        limit_choices_to={"tipo": "ALUNO"},
    )
    xp_total = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Progresso de gamificação"
        verbose_name_plural = "Progressos de gamificação"
        constraints = [
            models.CheckConstraint(
                condition=Q(xp_total__gte=0),
                name="gamif_xp_total_nao_negativo",
            ),
        ]

    def clean(self):
        super().clean()
        if self.aluno_id and self.aluno.tipo != "ALUNO":
            raise ValidationError(
                {"aluno": "Somente Alunos podem ter progresso de gamificação."}
            )

    def __str__(self):
        return f"{self.aluno} - {self.xp_total} XP"


class EventoXP(models.Model):
    """XP concedido a um aluno."""

    class Codigo(models.TextChoices):
        NOTIFICACAO_IMPORTANTE_VISUALIZADA = (
            "NOTIFICACAO_IMPORTANTE_VISUALIZADA",
            "Visualização de notificação importante",
        )
        MISSAO_CONCLUIDA = "MISSAO_CONCLUIDA", "Conclusão de missão"

    progresso = models.ForeignKey(
        Progresso,
        on_delete=models.CASCADE,
        related_name="eventos_xp",
    )
    codigo = models.CharField(max_length=40, choices=Codigo.choices)
    referencia_id = models.PositiveBigIntegerField()
    quantidade = models.PositiveIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de XP"
        verbose_name_plural = "Eventos de XP"
        ordering = ["-criado_em", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["progresso", "codigo", "referencia_id"],
                name="gamif_evento_origem_unico",
            ),
            models.CheckConstraint(
                condition=Q(quantidade__gt=0),
                name="gamif_evento_qtd_positiva",
            ),
            models.CheckConstraint(
                condition=Q(referencia_id__gt=0),
                name="gamif_evento_ref_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.progresso.aluno} - {self.quantidade} XP ({self.get_codigo_display()})"
