from django.contrib import admin

from usuarios.models import Usuario

from .models import Atividade, Disciplina
from notificacoes.services import criar_notificacoes_da_atividade

# Register your models here.

@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ("nome", "professor")
    search_fields = ("nome", "professor__username")
    filter_horizontal = ("alunos",)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "alunos":
            kwargs["queryset"] = Usuario.objects.filter(
                tipo=Usuario.Tipo.ALUNO
            )

        return super().formfield_for_manytomany(
            db_field,
            request,
            **kwargs,
        )


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "disciplina",
        "prazo",
        "criada_em"
    )

    list_filter = ("disciplina",)
    search_fields = ("titulo", "descricao")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not change:
            criar_notificacoes_da_atividade(obj)
