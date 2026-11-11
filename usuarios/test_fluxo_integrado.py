from datetime import timedelta

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from atividades.models import Atividade, Disciplina
from chat.models import Conversa, Mensagem
from gamificacao.models import EventoXP, Progresso
from notificacoes.models import Notificacao


class FluxoIntegradoTests(TestCase):
    senha = "Estudo!Dados_82Az"

    @classmethod
    def setUpTestData(cls):
        cls.professor = get_user_model().objects.create_user(
            username="professor", first_name="Carlos", password=cls.senha, tipo="PROFESSOR",
        )

    def abrir(self, cliente, url):
        response = cliente.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response

    def postar(self, cliente, url, dados=None, **headers):
        return cliente.post(url, data={
            **(dados or {}),
            "csrfmiddlewaretoken": cliente.cookies[settings.CSRF_COOKIE_NAME].value,
        }, **headers)

    def cadastrar_e_entrar(self, username):
        cliente = Client(enforce_csrf_checks=True)
        self.abrir(cliente, reverse("usuarios:cadastro"))
        response = self.postar(cliente, reverse("usuarios:cadastro"), {
            "username": username, "first_name": username.capitalize(),
            "email": f"{username}@example.com", "password1": self.senha, "password2": self.senha,
        })
        self.assertRedirects(response, reverse("usuarios:login"))
        self.assertNotIn(SESSION_KEY, cliente.session)
        self.entrar(cliente, username)
        usuario = get_user_model().objects.get(username=username)
        self.assertEqual(usuario.tipo, usuario.Tipo.ALUNO)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        return cliente, usuario

    def entrar(self, cliente, username):
        self.abrir(cliente, reverse("usuarios:login"))
        response = self.postar(cliente, reverse("usuarios:login"), {
            "username": username, "password": self.senha,
        })
        self.assertRedirects(response, reverse("usuarios:painel"))
        self.assertIn(SESSION_KEY, cliente.session)

    def test_do_cadastro_ao_ranking_e_chat_com_csrf_e_isolamento(self):
        # Os alunos se cadastram e entram pelas telas públicas.
        aluno, usuario = self.cadastrar_e_entrar("maria")
        externo, outro = self.cadastrar_e_entrar("joao")
        painel = self.abrir(aluno, reverse("usuarios:painel"))
        self.assertEqual(painel.context["disciplinas_total"], 0)
        self.assertEqual(painel.context["pontos"], 0)

        # O professor entra, cria a turma e matricula somente Maria.
        professor = Client(enforce_csrf_checks=True)
        self.entrar(professor, self.professor.username)
        self.abrir(professor, reverse("usuarios:criar_disciplina"))
        response = self.postar(professor, reverse("usuarios:criar_disciplina"), {"nome": "Estrutura de Dados"})
        disciplina = Disciplina.objects.get()
        url_disciplina = reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": disciplina.pk})
        self.assertRedirects(response, url_disciplina)
        self.assertEqual(disciplina.professor, self.professor)
        url_editar = reverse("usuarios:editar_disciplina", kwargs={"disciplina_id": disciplina.pk})
        self.abrir(professor, url_editar)
        response = self.postar(professor, url_editar, {"nome": disciplina.nome, "alunos": [usuario.pk]})
        self.assertRedirects(response, url_disciplina)
        self.assertCountEqual(disciplina.alunos.all(), [usuario])

        # Publicação com prazo de 36 horas gera um aviso IMPORTANTE.
        formulario = self.abrir(professor, f"{reverse('atividades:criar')}?disciplina={disciplina.pk}")
        self.assertEqual(formulario.context["form"]["disciplina"].value(), disciplina.pk)
        prazo = timezone.localtime(timezone.now() + timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M")
        response = self.postar(professor, reverse("atividades:criar"), {
            "titulo": "Trabalho de Pilhas", "descricao": "Implementar uma pilha em Python.",
            "disciplina": disciplina.pk, "prazo": prazo,
        })
        atividade = Atividade.objects.get()
        url_atividade = reverse("atividades:detalhe", kwargs={"atividade_id": atividade.pk})
        self.assertRedirects(response, url_atividade)
        aviso = Notificacao.objects.get()
        self.assertEqual(aviso.destinatario, usuario)
        self.assertEqual(aviso.prioridade, Notificacao.Prioridade.IMPORTANTE)
        self.assertEqual(timezone.localtime(atividade.prazo).strftime("%Y-%m-%dT%H:%M"), prazo)

        # O aluno navega pelas páginas e lê o aviso; repetir não duplica XP.
        self.assertContains(self.abrir(aluno, reverse("usuarios:disciplinas")), disciplina.nome)
        self.assertContains(self.abrir(aluno, url_disciplina), atividade.titulo)
        self.assertContains(self.abrir(aluno, reverse("atividades:lista")), atividade.titulo)
        self.assertContains(self.abrir(aluno, url_atividade), atividade.descricao)
        lista = self.abrir(aluno, reverse("notificacoes:lista"))
        self.assertEqual(lista.context["nao_visualizadas"], 1)
        self.assertFalse(Progresso.objects.filter(aluno=usuario).exists())
        url_aviso = reverse("notificacoes:visualizar_notificacao", kwargs={"notificacao_id": aviso.pk})
        response = self.postar(aluno, url_aviso, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        aviso.refresh_from_db()
        primeira_leitura = aviso.visualizada_em
        response = self.postar(aluno, url_aviso, HTTP_ACCEPT="text/html")
        self.assertRedirects(response, reverse("notificacoes:lista"))
        aviso.refresh_from_db()
        self.assertTrue(aviso.visualizada)
        self.assertIsNotNone(primeira_leitura)
        self.assertEqual(aviso.visualizada_em, primeira_leitura)
        self.assertEqual(Progresso.objects.get(aluno=usuario).xp_total, 10)
        self.assertEqual(EventoXP.objects.count(), 1)
        self.assertEqual(EventoXP.objects.get().referencia_id, aviso.pk)
        self.assertEqual(self.abrir(aluno, reverse("usuarios:painel")).context["pontos"], 10)
        ranking = self.abrir(aluno, reverse("gamificacao:ranking"))
        self.assertEqual(ranking.context["meus_pontos"], 10)
        self.assertEqual(ranking.context["alunos"][0].pk, usuario.pk)

        # Aluno e professor abrem a mesma conversa e trocam mensagens.
        url_abrir = reverse("chat:abrir_conversa", kwargs={"disciplina_id": disciplina.pk})
        self.abrir(aluno, reverse("chat:caixa_entrada"))
        response = self.postar(aluno, url_abrir)
        conversa = Conversa.objects.get()
        url_conversa = reverse("chat:conversa", kwargs={"conversa_id": conversa.pk})
        self.assertRedirects(response, url_conversa)
        url_envio = reverse("chat:enviar_mensagem", kwargs={"conversa_id": conversa.pk})
        self.abrir(aluno, url_conversa)
        primeira = self.postar(aluno, url_envio, {"conteudo": "  Olá, professor!  "}, HTTP_ACCEPT="application/json")
        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(primeira.json()["conteudo"], "Olá, professor!")
        self.abrir(professor, url_disciplina)
        self.assertRedirects(self.postar(professor, url_abrir, {"aluno_id": usuario.pk}), url_conversa)
        self.abrir(professor, url_conversa)
        segunda = self.postar(professor, url_envio, {"conteudo": "Olá, Maria!"}, HTTP_ACCEPT="application/json")
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(Conversa.objects.count(), 1)
        self.assertEqual(Mensagem.objects.count(), 2)
        url_historico = reverse("chat:historico_conversa", kwargs={"conversa_id": conversa.pk})
        historico = self.abrir(aluno, url_historico).json()["mensagens"]
        self.assertEqual([mensagem["id"] for mensagem in historico], [primeira.json()["id"], segunda.json()["id"]])
        self.assertEqual([mensagem["remetente_id"] for mensagem in historico], [usuario.pk, self.professor.pk])

        # O outro aluno não tem acesso à turma, aos avisos ou à conversa.
        for url in [url_disciplina, url_atividade]:
            self.assertEqual(externo.get(url).status_code, 404)
        self.assertEqual(self.abrir(externo, reverse("notificacoes:lista")).context["nao_visualizadas"], 0)
        self.assertEqual(self.postar(externo, url_aviso).status_code, 404)
        self.assertEqual(externo.get(url_conversa).status_code, 403)
        self.assertEqual(externo.get(url_historico).status_code, 403)
        self.assertEqual(self.postar(externo, url_envio, {"conteudo": "Tentativa indevida"}).status_code, 403)
        self.assertEqual(self.postar(externo, url_abrir).status_code, 403)
        self.assertFalse(Progresso.objects.filter(aluno=outro).exists())
        self.assertEqual(Mensagem.objects.count(), 2)
        self.assertEqual(EventoXP.objects.count(), 1)

        # O logout encerra as sessões e volta a exigir autenticação.
        for cliente in [aluno, professor, externo]:
            response = self.postar(cliente, reverse("usuarios:logout"))
            self.assertRedirects(response, reverse("usuarios:inicio"))
            self.assertNotIn(SESSION_KEY, cliente.session)
            self.assertRedirects(
                cliente.get(reverse("usuarios:painel")),
                f"{reverse('usuarios:login')}?next={reverse('usuarios:painel')}",
            )
