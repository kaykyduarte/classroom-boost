from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from atividades.models import Disciplina

from .models import Conversa, Mensagem
from .services import criar_ou_obter_conversa, enviar_mensagem


class ChatInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.professor2 = Usuario.objects.create_user(username="professor2", tipo="PROFESSOR")
        cls.aluno = Usuario.objects.create_user(username="aluno", tipo="ALUNO")
        cls.colega = Usuario.objects.create_user(username="colega", tipo="ALUNO")
        cls.externo = Usuario.objects.create_user(username="externo", tipo="ALUNO")
        cls.disciplina = Disciplina.objects.create(nome="Estrutura de Dados", professor=cls.professor)
        cls.disciplina.alunos.add(cls.aluno, cls.colega)
        cls.outra_disciplina = Disciplina.objects.create(nome="Outra turma", professor=cls.professor2)
        cls.outra_disciplina.alunos.add(cls.externo)

    def setUp(self):
        self.url_caixa = reverse("chat:caixa_entrada")
        self.url_abrir = reverse("chat:abrir_conversa", kwargs={"disciplina_id": self.disciplina.pk})

    def criar_conversa(self):
        return criar_ou_obter_conversa(self.aluno, self.professor, self.disciplina)

    def test_caixa_pagina_e_abertura_exigem_login(self):
        conversa = self.criar_conversa()
        urls = [
            self.url_caixa,
            reverse("chat:conversa", kwargs={"conversa_id": conversa.pk}),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('usuarios:login')}?next={url}")
        self.assertRedirects(
            self.client.post(self.url_abrir),
            f"{reverse('usuarios:login')}?next={self.url_abrir}",
        )

    def test_caixa_vazia_nao_cria_conversa(self):
        self.client.force_login(self.aluno)

        response = self.client.get(self.url_caixa)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat/caixa_entrada.html")
        self.assertContains(response, "Nenhuma conversa iniciada ainda.")
        self.assertQuerySetEqual(response.context["disciplinas"], [self.disciplina])
        self.assertFalse(Conversa.objects.exists())
        self.assertFalse(Mensagem.objects.exists())

    def test_caixa_mostra_somente_conversas_dos_participantes(self):
        conversa = self.criar_conversa()
        colega = criar_ou_obter_conversa(self.colega, self.professor, self.disciplina)
        privada = criar_ou_obter_conversa(self.externo, self.professor2, self.outra_disciplina)
        for usuario, esperadas in [(self.aluno, [conversa.pk]), (self.professor, [colega.pk, conversa.pk])]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.get(self.url_caixa)
                self.assertEqual([c.pk for c in response.context["conversas"]], esperadas)
                self.assertNotContains(response, reverse("chat:conversa", kwargs={"conversa_id": privada.pk}))
                self.assertNotContains(response, self.outra_disciplina.nome)

    def test_caixa_ordena_pela_ultima_mensagem_sem_novo_campo_no_model(self):
        primeira = self.criar_conversa()
        disciplina = Disciplina.objects.create(nome="Algoritmos", professor=self.professor)
        disciplina.alunos.add(self.aluno)
        segunda = criar_ou_obter_conversa(self.aluno, self.professor, disciplina)
        enviar_mensagem(primeira, self.professor, "Uma resposta recente.")
        self.client.force_login(self.aluno)

        response = self.client.get(self.url_caixa)

        conversas = list(response.context["conversas"])
        self.assertEqual([c.pk for c in conversas], [primeira.pk, segunda.pk])
        self.assertEqual(conversas[0].total_mensagens, 1)
        self.assertEqual(conversas[1].total_mensagens, 0)

    def test_aluno_abre_e_reutiliza_conversa_ignorando_identidade_enviada(self):
        self.client.force_login(self.aluno)

        primeira = self.client.post(self.url_abrir, data={"aluno_id": self.colega.pk})
        segunda = self.client.post(self.url_abrir)

        self.assertEqual(Conversa.objects.count(), 1)
        conversa = Conversa.objects.get()
        self.assertEqual(conversa.aluno, self.aluno)
        self.assertEqual(conversa.professor, self.professor)
        self.assertEqual(conversa.disciplina, self.disciplina)
        url = reverse("chat:conversa", kwargs={"conversa_id": conversa.pk})
        self.assertRedirects(primeira, url)
        self.assertRedirects(segunda, url)

    def test_professor_abre_conversa_com_aluno_matriculado(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url_abrir, data={"aluno_id": self.aluno.pk})

        conversa = Conversa.objects.get()
        self.assertEqual(conversa.aluno, self.aluno)
        self.assertEqual(conversa.professor, self.professor)
        self.assertRedirects(response, reverse("chat:conversa", kwargs={"conversa_id": conversa.pk}))

    def test_abertura_por_get_nao_cria_conversa(self):
        self.client.force_login(self.aluno)

        response = self.client.get(self.url_abrir)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(Conversa.objects.exists())

    def test_abertura_sem_csrf_nao_cria_conversa(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno)

        response = cliente.post(self.url_abrir)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Conversa.objects.exists())

    def test_usuarios_sem_vinculo_nao_iniciam_conversa(self):
        administrador = get_user_model().objects.create_superuser(username="admin")
        for usuario in [self.externo, self.professor2, administrador]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.post(self.url_abrir, data={"aluno_id": self.aluno.pk})
                self.assertEqual(response.status_code, 403)
        self.assertFalse(Conversa.objects.exists())

    def test_professor_nao_inicia_com_aluno_invalido_ou_nao_matriculado(self):
        self.client.force_login(self.professor)
        for aluno_id in ["", "invalido", self.externo.pk, self.professor.pk, self.externo.pk + 1000]:
            with self.subTest(aluno_id=aluno_id):
                self.assertEqual(self.client.post(self.url_abrir, data={"aluno_id": aluno_id}).status_code, 404)
        self.assertFalse(Conversa.objects.exists())

    def test_participantes_visualizam_pagina_com_historico_ordenado(self):
        conversa = self.criar_conversa()
        primeira = enviar_mensagem(conversa, self.aluno, "Olá, professor!")
        segunda = enviar_mensagem(conversa, self.professor, "Olá, aluno!")
        url = reverse("chat:conversa", kwargs={"conversa_id": conversa.pk})
        for usuario, outro in [(self.aluno, self.professor), (self.professor, self.aluno)]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "chat/conversa.html")
                self.assertEqual(response.context["outro_participante"], outro)
                self.assertQuerySetEqual(response.context["historico"], [primeira, segunda])
                self.assertContains(response, 'src="/static/js/chat.js"')
                self.assertContains(response, reverse("chat:enviar_mensagem", kwargs={"conversa_id": conversa.pk}))

    def test_usuario_externo_e_admin_nao_visualizam_pagina_privada(self):
        conversa = self.criar_conversa()
        mensagem = enviar_mensagem(conversa, self.aluno, "Uma mensagem privada.")
        administrador = get_user_model().objects.create_superuser(username="admin")
        url = reverse("chat:conversa", kwargs={"conversa_id": conversa.pk})
        for usuario in [self.colega, self.externo, administrador]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, mensagem.conteudo, status_code=403)

    def test_conversa_e_disciplina_inexistentes_retornam_404(self):
        self.client.force_login(self.aluno)

        self.assertEqual(self.client.get(reverse("chat:conversa", kwargs={"conversa_id": 999})).status_code, 404)
        self.assertEqual(self.client.post(reverse("chat:abrir_conversa", kwargs={"disciplina_id": 999})).status_code, 404)

    def test_formulario_sem_javascript_envia_e_retorna_a_conversa(self):
        conversa = self.criar_conversa()
        self.client.force_login(self.aluno)

        response = self.client.post(
            reverse("chat:enviar_mensagem", kwargs={"conversa_id": conversa.pk}),
            data={"conteudo": "  Olá, professor!  ", "remetente_id": self.professor.pk},
            HTTP_ACCEPT="text/html", follow=True,
        )

        self.assertRedirects(response, reverse("chat:conversa", kwargs={"conversa_id": conversa.pk}))
        mensagem = Mensagem.objects.get()
        self.assertEqual(mensagem.conteudo, "Olá, professor!")
        self.assertEqual(mensagem.remetente, self.aluno)
        self.assertContains(response, mensagem.conteudo)

    def test_formulario_html_vazio_exibe_erro_sem_criar_mensagem(self):
        conversa = self.criar_conversa()
        self.client.force_login(self.aluno)

        response = self.client.post(
            reverse("chat:enviar_mensagem", kwargs={"conversa_id": conversa.pk}),
            data={"conteudo": "   "}, HTTP_ACCEPT="text/html",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "chat/conversa.html")
        self.assertContains(response, "O conteúdo da mensagem não pode estar vazio.", status_code=400)
        self.assertFalse(Mensagem.objects.exists())

    def test_formulario_html_nao_expoe_historico_a_remetente_externo(self):
        conversa = self.criar_conversa()
        mensagem = enviar_mensagem(conversa, self.aluno, "Conteúdo privado.")
        self.client.force_login(self.colega)

        response = self.client.post(
            reverse("chat:enviar_mensagem", kwargs={"conversa_id": conversa.pk}),
            data={"conteudo": "   "}, HTTP_ACCEPT="text/html",
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, mensagem.conteudo, status_code=403)
        self.assertEqual(Mensagem.objects.count(), 1)

    def test_pagina_escapa_html_no_conteudo_das_mensagens(self):
        conversa = self.criar_conversa()
        enviar_mensagem(conversa, self.aluno, '<script>alert("teste")</script>')
        self.client.force_login(self.professor)

        response = self.client.get(reverse("chat:conversa", kwargs={"conversa_id": conversa.pk}))

        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("teste")</script>')

    def test_historico_existente_permanece_com_os_participantes_apos_remocao_da_turma(self):
        conversa = self.criar_conversa()
        enviar_mensagem(conversa, self.aluno, "Histórico anterior.")
        self.disciplina.alunos.remove(self.aluno)
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("chat:conversa", kwargs={"conversa_id": conversa.pk}))

        self.assertContains(response, "Histórico anterior.")
        self.assertEqual(self.client.post(self.url_abrir).status_code, 403)

    def test_disciplina_tem_formularios_de_abertura_para_aluno_e_professor(self):
        url = reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk})
        for usuario in [self.aluno, self.professor]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertContains(self.client.get(url), f'action="{self.url_abrir}"')

    def test_admin_nao_ve_caixa_de_entrada_de_outros_usuarios(self):
        self.criar_conversa()
        administrador = get_user_model().objects.create_superuser(username="admin")
        self.client.force_login(administrador)

        response = self.client.get(self.url_caixa)

        self.assertQuerySetEqual(response.context["conversas"], [])
        self.assertQuerySetEqual(response.context["disciplinas"], [])

    def test_fluxo_de_abertura_e_troca_de_mensagens_com_csrf_valido(self):
        aluno = Client(enforce_csrf_checks=True)
        aluno.force_login(self.aluno)
        aluno.get(self.url_caixa)

        response = aluno.post(self.url_abrir, data={
            "csrfmiddlewaretoken": aluno.cookies["csrftoken"].value,
        })

        self.assertEqual(response.status_code, 302)
        conversa = Conversa.objects.get()
        url_pagina = reverse("chat:conversa", kwargs={"conversa_id": conversa.pk})
        url_envio = reverse("chat:enviar_mensagem", kwargs={"conversa_id": conversa.pk})
        aluno.get(url_pagina)
        primeira = aluno.post(url_envio, data={
            "csrfmiddlewaretoken": aluno.cookies["csrftoken"].value,
            "conteudo": "Olá, professor!",
        }, HTTP_ACCEPT="application/json")

        professor = Client(enforce_csrf_checks=True)
        professor.force_login(self.professor)
        professor.get(url_pagina)
        segunda = professor.post(url_envio, data={
            "csrfmiddlewaretoken": professor.cookies["csrftoken"].value,
            "conteudo": "Olá, aluno!",
        }, HTTP_ACCEPT="application/json")

        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(primeira.json()["remetente_id"], self.aluno.pk)
        self.assertEqual(segunda.json()["remetente_id"], self.professor.pk)
        historico = aluno.get(reverse("chat:historico_conversa", kwargs={"conversa_id": conversa.pk}))
        self.assertEqual(historico.status_code, 200)
        self.assertEqual(
            [mensagem["id"] for mensagem in historico.json()["mensagens"]],
            [primeira.json()["id"], segunda.json()["id"]],
        )
        self.assertEqual(Mensagem.objects.filter(conversa=conversa).count(), 2)
