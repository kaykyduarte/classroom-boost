from django.conf import settings
from django.db import models

# Create your models here.

class Disciplina(models.Model):
    nome = models.CharField(max_length=100)

    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="disciplinas_lecionadas",
        limit_choices_to={"tipo": "PROFESSOR"},
    )

    alunos = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="disciplinas_matriculadas",
        blank=True,
    )

    def __str__(self):
        return self.nome


class Atividade(models.Model):
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)

    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.PROTECT,
        related_name="atividades",
    )

    prazo = models.DateTimeField()
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo
