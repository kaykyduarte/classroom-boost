from django import forms
from django.contrib.auth.forms import UserCreationForm

from atividades.models import Disciplina

from .models import Usuario


class CadastroAlunoForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-mail")
    first_name = forms.CharField(max_length=150, required=True, label="Nome")
    last_name = forms.CharField(max_length=150, required=False, label="Sobrenome")

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Usuário"}

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.tipo = Usuario.Tipo.ALUNO
        if commit:
            usuario.save()
        return usuario


class DisciplinaForm(forms.ModelForm):
    class Meta:
        model = Disciplina
        fields = ("nome", "alunos")
        labels = {"nome": "Nome da disciplina", "alunos": "Alunos matriculados"}
        widgets = {"alunos": forms.CheckboxSelectMultiple()}
        help_texts = {"alunos": "Marque os alunos que devem fazer parte da turma."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["alunos"].queryset = Usuario.objects.filter(
            tipo=Usuario.Tipo.ALUNO,
        ).order_by("first_name", "username")
        self.fields["alunos"].required = False
