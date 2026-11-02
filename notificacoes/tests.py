from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.shortcuts import resolve_url

from atividades.models import Atividade, Disciplina
from notificacoes.models import Notificacao


class NotificacaoTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()

        self.professor = Usuario.objects.create_user(
            username="professor",
            password="senha-teste",
            tipo=Usuario.Tipo.PROFESSOR,
        )

        self.aluno1 = Usuario.objects.create_user(
            username="aluno1",
            password="senha-teste",
            tipo=Usuario.Tipo.ALUNO,
        )

        self.aluno2 = Usuario.objects.create_user(
            username="aluno2",
            password="senha-teste",
            tipo=Usuario.Tipo.ALUNO,
        )

        self.disciplina = Disciplina.objects.create(
            nome="Estrutura de Dados",
            professor=self.professor,
        )

        self.disciplina.alunos.add(self.aluno1, self.aluno2)

        self.atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas",
            descricao="Implementar uma pilha em python",
            disciplina=self.disciplina,
            prazo=timezone.now() + timedelta(days=3),
        )

        self.notificacao = Notificacao.objects.create(
            destinatario=self.aluno1,
            atividade=self.atividade,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE,
            titulo="Nova atividade disponível",
            mensagem="Uma nova atividade foi publicada",
            prioridade=Notificacao.Prioridade.NORMAL,
            visualizada=False,
        )


    def test_aluno_visualiza_sua_notificacao(self):
        self.client.force_login(self.aluno1)

        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": self.notificacao.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)

        self.notificacao.refresh_from_db()

        self.assertTrue(self.notificacao.visualizada)
        self.assertIsNotNone(self.notificacao.visualizada_em)


    def test_aluno_nao_visualiza_notificacao_de_outro(self):
        self.client.force_login(self.aluno2)

        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": self.notificacao.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

        self.notificacao.refresh_from_db()

        self.assertFalse(self.notificacao.visualizada)
        self.assertIsNone(self.notificacao.visualizada_em)


    def test_visualizacao_idempotente(self):
        self.client.force_login(self.aluno1)

        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": self.notificacao.pk},
        )

        primeira_response = self.client.post(url)
        self.assertEqual(primeira_response.status_code, 200)

        self.notificacao.refresh_from_db()
        primeira_visualizacao = self.notificacao.visualizada_em
        self.assertIsNotNone(primeira_visualizacao)

        segunda_response = self.client.post(url)
        self.assertEqual(segunda_response.status_code, 200)

        self.notificacao.refresh_from_db()

        self.assertTrue(self.notificacao.visualizada)
        self.assertEqual(
            self.notificacao.visualizada_em,
            primeira_visualizacao,
        )


    def test_get_nao_permitido(self):
        self.client.force_login(self.aluno1)

        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": self.notificacao.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)

        self.notificacao.refresh_from_db()

        self.assertFalse(self.notificacao.visualizada)
        self.assertIsNone(self.notificacao.visualizada_em)   


    def test_usuario_nao_autenticado(self):
        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": self.notificacao.pk},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f"{resolve_url(settings.LOGIN_URL)}?next={url}",
            fetch_redirect_response=False,
        )

        self.notificacao.refresh_from_db()

        self.assertFalse(self.notificacao.visualizada)
        self.assertIsNone(self.notificacao.visualizada_em)


    def test_notificacao_inexistente(self):
        self.client.force_login(self.aluno1)

        id_inexistente = self.notificacao.pk + 1000

        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": id_inexistente},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)


    def test_post_sem_csrf_bloqueado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno1)

        url = reverse(
            "notificacoes:visualizar_notificacao",
            kwargs={"notificacao_id": self.notificacao.pk},
        )

        response = cliente.post(url)

        self.assertEqual(response.status_code, 403)

        self.notificacao.refresh_from_db()

        self.assertFalse(self.notificacao.visualizada)
        self.assertIsNone(self.notificacao.visualizada_em)
