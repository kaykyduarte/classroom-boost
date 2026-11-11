from django.urls import path

from . import views

app_name = "atividades"

urlpatterns = [
    path("", views.lista_atividades, name="lista"),
    path("nova/", views.criar_atividade, name="criar"),
    path("<int:atividade_id>/", views.detalhe_atividade, name="detalhe"),
]
