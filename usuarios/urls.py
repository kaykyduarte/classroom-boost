from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("painel/", views.painel, name="painel"),
    path("disciplinas/", views.minhas_disciplinas, name="disciplinas"),
    path("disciplinas/nova/", views.criar_disciplina, name="criar_disciplina"),
    path(
        "disciplinas/<int:disciplina_id>/editar/",
        views.editar_disciplina,
        name="editar_disciplina",
    ),
    path(
        "disciplinas/<int:disciplina_id>/",
        views.detalhe_disciplina,
        name="detalhe_disciplina",
    ),
    path(
        "conta/entrar/",
        auth_views.LoginView.as_view(
            template_name="usuarios/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("conta/sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("conta/cadastro/", views.cadastro_aluno, name="cadastro"),
]
