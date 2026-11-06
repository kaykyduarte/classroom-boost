from django.contrib import admin

from .models import EventoXP, Progresso


@admin.register(Progresso)
class ProgressoAdmin(admin.ModelAdmin):
    list_display = ("aluno", "xp_total", "criado_em", "atualizado_em")
    search_fields = ("aluno__username", "aluno__first_name", "aluno__last_name")
    readonly_fields = ("aluno", "xp_total", "criado_em", "atualizado_em")

    def has_add_permission(self, request):
        # O progresso deve ser criado pelo serviço conceder_xp().
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoXP)
class EventoXPAdmin(admin.ModelAdmin):
    list_display = ("progresso", "codigo", "referencia_id", "quantidade", "criado_em")
    list_filter = ("codigo", "criado_em")
    search_fields = ("progresso__aluno__username", "progresso__aluno__first_name")
    readonly_fields = ("progresso", "codigo", "referencia_id", "quantidade", "criado_em")

    def has_add_permission(self, request):
        # O histórico de recompensas não deve ser editado manualmente.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
