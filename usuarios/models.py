from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

class Usuario(AbstractUser):
    class Tipo(models.TextChoices):
        ALUNO = "ALUNO", "Aluno"
        PROFESSOR = "PROFESSOR", "Professor"

    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
        blank=True,
    )
