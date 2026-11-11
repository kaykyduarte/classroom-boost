from django import forms
from django.utils import timezone

from .models import Atividade, Disciplina


class AtividadeForm(forms.ModelForm):
    prazo = forms.DateTimeField(
        label="Prazo de entrega",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = Atividade
        fields = ("titulo", "descricao", "disciplina", "prazo")
        labels = {"titulo": "Título", "descricao": "Descrição", "disciplina": "Disciplina"}
        widgets = {"descricao": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, professor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disciplina"].queryset = Disciplina.objects.filter(
            professor=professor,
        ).order_by("nome", "pk")
        self.fields["prazo"].help_text = "Informe a data e a hora no horário de Brasília (São Paulo)."

    def clean_prazo(self):
        prazo = self.cleaned_data["prazo"]
        if prazo <= timezone.now():
            raise forms.ValidationError("O prazo precisa estar no futuro.")
        return prazo
