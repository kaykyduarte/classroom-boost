from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.shortcuts import resolve_url

from atividades.models import Atividade, Disciplina
from notificacoes.models import Notificacao
from gamificacao.models import EventoXP, Progresso

from .services import marcar_como_visualizado


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

        self.progresso, _ = Progresso.objects.get_or_create(
            aluno=self.aluno1,
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

    def test_notificacao_normal_nao_concede_xp(self):
        self.notificacao.prioridade = Notificacao.Prioridade.NORMAL
        self.notificacao.save(update_fields=["prioridade"])

        marcar_como_visualizado(self.notificacao.pk, self.aluno1)

        self.notificacao.refresh_from_db()
        self.progresso.refresh_from_db()

        self.assertTrue(self.notificacao.visualizada)
        self.assertEqual(self.progresso.xp_total, 0)
        self.assertEqual(EventoXP.objects.count(), 0)

    def test_notificacao_importante_concede_10_xp(self):
        self.notificacao.prioridade = Notificacao.Prioridade.IMPORTANTE
        self.notificacao.save(update_fields=["prioridade"])

        marcar_como_visualizado(self.notificacao.pk, self.aluno1)

        self.notificacao.refresh_from_db()
        self.progresso.refresh_from_db()

        self.assertTrue(self.notificacao.visualizada)
        self.assertEqual(self.progresso.xp_total, 10)
        self.assertEqual(EventoXP.objects.count(), 1)

        evento = EventoXP.objects.get()
        self.assertEqual(evento.progresso_id, self.progresso.pk)
        self.assertEqual(
            evento.codigo,
            EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
        )
        self.assertEqual(evento.referencia_id, self.notificacao.pk)
        self.assertEqual(evento.quantidade, 10)

    def test_notificacao_urgente_concede_10_xp(self):
        self.notificacao.prioridade = Notificacao.Prioridade.URGENTE
        self.notificacao.save(update_fields=["prioridade"])

        marcar_como_visualizado(self.notificacao.pk, self.aluno1)

        self.notificacao.refresh_from_db()
        self.progresso.refresh_from_db()

        self.assertTrue(self.notificacao.visualizada)
        self.assertEqual(self.progresso.xp_total, 10)
        self.assertEqual(EventoXP.objects.count(), 1)

        evento = EventoXP.objects.get()
        self.assertEqual(evento.progresso_id, self.progresso.pk)
        self.assertEqual(
            evento.codigo,
            EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
        )
        self.assertEqual(evento.referencia_id, self.notificacao.pk)
        self.assertEqual(evento.quantidade, 10)

    def test_visualizar_duas_vezes_nao_duplica_xp(self):
        self.notificacao.prioridade = Notificacao.Prioridade.IMPORTANTE
        self.notificacao.save(update_fields=["prioridade"])

        marcar_como_visualizado(self.notificacao.pk, self.aluno1)
        marcar_como_visualizado(self.notificacao.pk, self.aluno1)

        self.progresso.refresh_from_db()

        self.assertEqual(self.progresso.xp_total, 10)
        self.assertEqual(EventoXP.objects.count(), 1)

    def test_notificacao_de_outro_aluno_nao_concede_xp(self):
        self.notificacao.prioridade = Notificacao.Prioridade.IMPORTANTE
        self.notificacao.save(update_fields=["prioridade"])

        progresso_aluno2, _ = Progresso.objects.get_or_create(
            aluno=self.aluno2,
        )

        with self.assertRaises(Notificacao.DoesNotExist):
            marcar_como_visualizado(
                self.notificacao.pk,
                self.aluno2,
            )

        self.notificacao.refresh_from_db()
        self.progresso.refresh_from_db()
        progresso_aluno2.refresh_from_db()

        self.assertFalse(self.notificacao.visualizada)
        self.assertIsNone(self.notificacao.visualizada_em)
        self.assertEqual(self.progresso.xp_total, 0)
        self.assertEqual(progresso_aluno2.xp_total, 0)
        self.assertEqual(EventoXP.objects.count(), 0)


class ListaNotificacoesViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.aluno = Usuario.objects.create_user(username="aluno", tipo="ALUNO")
        cls.aluno2 = Usuario.objects.create_user(username="aluno2", tipo="ALUNO")
        cls.disciplina = Disciplina.objects.create(nome="Estrutura de Dados", professor=cls.professor)
        cls.disciplina.alunos.add(cls.aluno, cls.aluno2)
        cls.outra_disciplina = Disciplina.objects.create(nome="Outra disciplina", professor=cls.professor)
        cls.atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas", disciplina=cls.disciplina,
            prazo=timezone.now() + timedelta(hours=12),
        )
        atividade_lida = Atividade.objects.create(
            titulo="Trabalho de Filas", disciplina=cls.disciplina,
            prazo=timezone.now() + timedelta(days=3),
        )
        atividade_oculta = Atividade.objects.create(
            titulo="Atividade de turma sem matrícula", disciplina=cls.outra_disciplina,
            prazo=timezone.now() + timedelta(days=3),
        )
        cls.notificacao = Notificacao.objects.create(
            destinatario=cls.aluno, atividade=cls.atividade,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE, prioridade=Notificacao.Prioridade.URGENTE,
            titulo="Aviso urgente do aluno", mensagem="Uma nova atividade foi publicada.",
        )
        cls.lida = Notificacao.objects.create(
            destinatario=cls.aluno, atividade=atividade_lida,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE, prioridade=Notificacao.Prioridade.NORMAL,
            titulo="Aviso já visualizado", mensagem="Uma atividade anterior.",
            visualizada=True, visualizada_em=timezone.now(),
        )
        cls.aviso_outro_aluno = Notificacao.objects.create(
            destinatario=cls.aluno2, atividade=cls.atividade,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE, prioridade=Notificacao.Prioridade.URGENTE,
            titulo="Aviso privado de outro aluno", mensagem="Mensagem privada.",
        )
        cls.oculta = Notificacao.objects.create(
            destinatario=cls.aluno, atividade=atividade_oculta,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE, titulo="Aviso de turma sem matrícula",
            mensagem="Aviso que não deve aparecer.",
        )

    def setUp(self):
        self.url = reverse("notificacoes:lista")
        self.url_marcar = reverse(
            "notificacoes:visualizar_notificacao", kwargs={"notificacao_id": self.notificacao.pk},
        )

    def test_listagem_exige_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(response, f"{reverse('usuarios:login')}?next={self.url}")

    def test_listagem_exibe_apenas_avisos_do_usuario_em_turmas_atuais(self):
        self.client.force_login(self.aluno)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notificacoes/lista.html")
        self.assertQuerySetEqual(response.context["notificacoes"], [self.notificacao, self.lida])
        self.assertEqual(response.context["nao_visualizadas"], 1)
        self.assertContains(response, self.notificacao.titulo)
        self.assertContains(response, self.lida.titulo)
        self.assertNotContains(response, self.aviso_outro_aluno.titulo)
        self.assertNotContains(response, self.oculta.titulo)
        self.assertContains(response, reverse("atividades:detalhe", kwargs={"atividade_id": self.atividade.pk}))
        self.assertContains(response, 'src="/static/js/notificacoes.js"')
        self.assertContains(response, f'action="{self.url_marcar}"')
        url_lida = reverse("notificacoes:visualizar_notificacao", kwargs={"notificacao_id": self.lida.pk})
        self.assertNotContains(response, f'action="{url_lida}"')

    def test_abrir_lista_nao_marca_avisos_nem_concede_xp(self):
        self.client.force_login(self.aluno)

        self.client.get(self.url)

        self.notificacao.refresh_from_db()
        self.assertFalse(self.notificacao.visualizada)
        self.assertIsNone(self.notificacao.visualizada_em)
        self.assertFalse(EventoXP.objects.exists())
        self.assertFalse(Progresso.objects.exists())

    def test_usuario_sem_avisos_ve_lista_vazia(self):
        self.client.force_login(self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nao_visualizadas"], 0)
        self.assertContains(response, "Você ainda não tem notificações.")

    def test_post_json_marca_aviso_e_concede_xp_uma_unica_vez(self):
        self.client.force_login(self.aluno)

        primeira = self.client.post(self.url_marcar, HTTP_ACCEPT="application/json")
        self.notificacao.refresh_from_db()
        primeira_data = self.notificacao.visualizada_em
        segunda = self.client.post(self.url_marcar, HTTP_ACCEPT="application/json")

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primeira.json(), {"success": True, "message": "Notificação visualizada"})
        self.notificacao.refresh_from_db()
        self.assertTrue(self.notificacao.visualizada)
        self.assertIsNotNone(primeira_data)
        self.assertEqual(self.notificacao.visualizada_em, primeira_data)
        self.assertEqual(Progresso.objects.get(aluno=self.aluno).xp_total, 10)
        self.assertEqual(EventoXP.objects.count(), 1)

    def test_formulario_html_retorna_a_lista_com_contador_atualizado(self):
        self.client.force_login(self.aluno)

        response = self.client.post(
            self.url_marcar,
            HTTP_ACCEPT="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            follow=True,
        )

        self.assertRedirects(response, self.url)
        self.assertEqual(response.context["nao_visualizadas"], 0)
        self.assertContains(response, "Notificação marcada como lida.")
        self.assertNotContains(response, f'action="{self.url_marcar}"')
        self.assertEqual(Progresso.objects.get(aluno=self.aluno).xp_total, 10)

    def test_aluno_removido_nao_visualiza_aviso_nem_recebe_xp(self):
        self.disciplina.alunos.remove(self.aluno)
        self.client.force_login(self.aluno)

        response = self.client.post(self.url_marcar)

        self.assertEqual(response.status_code, 404)
        self.notificacao.refresh_from_db()
        self.assertFalse(self.notificacao.visualizada)
        self.assertFalse(EventoXP.objects.exists())
        self.assertFalse(Progresso.objects.exists())

    def test_aluno_nao_marca_aviso_de_outro_destinatario(self):
        self.client.force_login(self.aluno2)

        response = self.client.post(self.url_marcar, HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 404)
        self.notificacao.refresh_from_db()
        self.assertFalse(self.notificacao.visualizada)
        self.assertFalse(EventoXP.objects.exists())

    def test_formulario_com_csrf_valido_permite_leitura(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno)
        cliente.get(self.url)

        response = cliente.post(
            self.url_marcar,
            data={"csrfmiddlewaretoken": cliente.cookies[settings.CSRF_COOKIE_NAME].value},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.notificacao.refresh_from_db()
        self.assertTrue(self.notificacao.visualizada)

    def test_painel_tem_link_para_lista_e_aviso(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertContains(response, f'href="{self.url}"')
        self.assertContains(response, f'href="{self.url}#notificacao-{self.notificacao.pk}"')
