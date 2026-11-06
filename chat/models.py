from django.db import models
from django.conf import settings

from atividades.models import  Disciplina

# Create your models here.


class Conversa(models.Model):
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conversas_como_aluno",
        limit_choices_to={"tipo": "ALUNO"},        
    )

    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conversas_como_professor",
        limit_choices_to={"tipo": "PROFESSOR"},
    )

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.PROTECT,
        related_name="conversas",
    )

    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "professor", "disciplina"],
                name="unique_conversa_aluno_professor_disciplina",
            ),
        ]

class Mensagem(models.Model):
    conversa = models.ForeignKey(
        Conversa,
        on_delete=models.CASCADE,
        related_name="mensagens",
    )

    remetente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mensagens_enviadas",
    )

    conteudo = models.TextField()

    enviada_em = models.DateTimeField(auto_now_add=True)
    