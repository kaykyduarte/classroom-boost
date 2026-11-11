from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from atividades.models import Atividade, Disciplina
from gamificacao.models import Progresso
from notificacoes.models import Notificacao
from notificacoes.services import criar_notificacoes_da_atividade


class AutenticacaoViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.aluno = get_user_model().objects.create_user(
            username="aluno",
            password="senha-teste",
            tipo=get_user_model().Tipo.ALUNO,
        )

    def test_pagina_login_exibe_formulario(self):
        response = self.client.get(reverse("usuarios:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/login.html")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_login_valido_autentica_e_abre_painel(self):
        response = self.client.post(
            reverse("usuarios:login"),
            data={"username": "aluno", "password": "senha-teste"},
            follow=True,
        )

        self.assertRedirects(response, reverse("usuarios:painel"))
        self.assertEqual(self.client.session[SESSION_KEY], str(self.aluno.pk))
        self.assertContains(response, "Olá, aluno!")
        self.assertContains(response, reverse("usuarios:logout"))

    def test_senha_incorreta_nao_autentica(self):
        response = self.client.post(
            reverse("usuarios:login"),
            data={"username": "aluno", "password": "senha-incorreta"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_preserva_destino_next(self):
        destino = reverse("chat:historico_conversa", kwargs={"conversa_id": 999})
        response = self.client.post(
            reverse("usuarios:login"),
            data={"username": "aluno", "password": "senha-teste", "next": destino},
        )

        self.assertRedirects(response, destino, fetch_redirect_response=False)

    def test_login_rejeita_redirecionamento_externo(self):
        response = self.client.post(
            reverse("usuarios:login"),
            data={
                "username": "aluno",
                "password": "senha-teste",
                "next": "https://example.com/",
            },
        )

        self.assertRedirects(response, reverse("usuarios:painel"))

    def test_usuario_autenticado_nao_precisa_fazer_login_novamente(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:login"))

        self.assertRedirects(response, reverse("usuarios:painel"))

    def test_logout_por_post_encerra_sessao(self):
        self.client.force_login(self.aluno)

        response = self.client.post(reverse("usuarios:logout"))

        self.assertRedirects(response, reverse("usuarios:inicio"))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_logout_por_get_nao_encerra_sessao(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:logout"))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.aluno.pk))

    def test_logout_sem_csrf_nao_encerra_sessao(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno)

        response = cliente.post(reverse("usuarios:logout"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(cliente.session[SESSION_KEY], str(self.aluno.pk))


class CadastroAlunoViewTests(TestCase):
    def setUp(self):
        self.url = reverse("usuarios:cadastro")
        self.dados = {
            "username": "novo_aluno",
            "first_name": "Maria",
            "last_name": "Silva",
            "email": "maria@example.com",
            "password1": "Estudo!Pilha_72Az",
            "password2": "Estudo!Pilha_72Az",
        }

    def test_pagina_cadastro_exibe_formulario(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/cadastro.html")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotIn("tipo", response.context["form"].fields)

    def test_cadastro_cria_aluno_e_permite_login(self):
        response = self.client.post(self.url, data=self.dados, follow=True)

        self.assertRedirects(response, reverse("usuarios:login"))
        self.assertContains(response, "Cadastro realizado!")
        self.assertEqual(get_user_model().objects.count(), 1)
        aluno = get_user_model().objects.get(username=self.dados["username"])
        self.assertEqual(aluno.tipo, aluno.Tipo.ALUNO)
        self.assertEqual(aluno.first_name, "Maria")
        self.assertEqual(aluno.last_name, "Silva")
        self.assertEqual(aluno.email, "maria@example.com")
        self.assertNotEqual(aluno.password, self.dados["password1"])
        self.assertTrue(aluno.check_password(self.dados["password1"]))
        self.assertNotIn(SESSION_KEY, self.client.session)

        response = self.client.post(
            reverse("usuarios:login"),
            data={"username": aluno.username, "password": self.dados["password1"]},
        )

        self.assertRedirects(response, reverse("usuarios:painel"))
        self.assertEqual(self.client.session[SESSION_KEY], str(aluno.pk))

    def test_cadastro_nao_permite_escolher_papel_ou_privilegios(self):
        response = self.client.post(
            self.url,
            data={
                **self.dados,
                "tipo": "PROFESSOR",
                "is_staff": "True",
                "is_superuser": "True",
            },
        )

        self.assertRedirects(response, reverse("usuarios:login"))
        aluno = get_user_model().objects.get(username=self.dados["username"])
        self.assertEqual(aluno.tipo, aluno.Tipo.ALUNO)
        self.assertFalse(aluno.is_staff)
        self.assertFalse(aluno.is_superuser)

    def test_cadastro_rejeita_usuario_duplicado(self):
        get_user_model().objects.create_user(username=self.dados["username"])

        response = self.client.post(self.url, data=self.dados)

        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_cadastro_rejeita_senhas_invalidas(self):
        for senha1, senha2 in [
            (self.dados["password1"], "SenhaDiferente!72"),
            ("123", "123"),
        ]:
            with self.subTest(senha1=senha1):
                response = self.client.post(
                    self.url,
                    data={**self.dados, "password1": senha1, "password2": senha2},
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("password2", response.context["form"].errors)
                self.assertEqual(get_user_model().objects.count(), 0)

    def test_cadastro_valida_nome_e_email(self):
        for campo, valor in [("first_name", ""), ("email", ""), ("email", "invalido")]:
            with self.subTest(campo=campo, valor=valor):
                response = self.client.post(
                    self.url,
                    data={**self.dados, campo: valor},
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
                self.assertEqual(get_user_model().objects.count(), 0)

    def test_usuario_autenticado_nao_cria_outra_conta(self):
        aluno = get_user_model().objects.create_user(
            username="aluno_existente", tipo=get_user_model().Tipo.ALUNO,
        )
        self.client.force_login(aluno)

        response = self.client.post(self.url, data=self.dados)

        self.assertRedirects(response, reverse("usuarios:painel"))
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(self.client.session[SESSION_KEY], str(aluno.pk))

    def test_cadastro_sem_csrf_nao_cria_usuario(self):
        cliente = Client(enforce_csrf_checks=True)

        response = cliente.post(self.url, data=self.dados)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(get_user_model().objects.count(), 0)


class PainelViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(
            username="professor", tipo=Usuario.Tipo.PROFESSOR,
        )
        cls.professor2 = Usuario.objects.create_user(
            username="professor2", tipo=Usuario.Tipo.PROFESSOR,
        )
        cls.aluno = Usuario.objects.create_user(
            username="aluno", tipo=Usuario.Tipo.ALUNO,
        )
        cls.aluno2 = Usuario.objects.create_user(
            username="aluno2", tipo=Usuario.Tipo.ALUNO,
        )
        cls.disciplina = Disciplina.objects.create(
            nome="Estrutura de Dados", professor=cls.professor,
        )
        cls.disciplina.alunos.add(cls.aluno)
        cls.disciplina2 = Disciplina.objects.create(
            nome="Turma privada de outro professor", professor=cls.professor2,
        )
        cls.disciplina2.alunos.add(cls.aluno2)
        cls.atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas",
            disciplina=cls.disciplina,
            prazo=timezone.now() + timedelta(days=3),
        )
        cls.atividade2 = Atividade.objects.create(
            titulo="Atividade privada de outra turma",
            disciplina=cls.disciplina2,
            prazo=timezone.now() + timedelta(days=3),
        )
        cls.notificacao = Notificacao.objects.create(
            destinatario=cls.aluno,
            atividade=cls.atividade,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE,
            titulo="Aviso do aluno",
            mensagem="Uma atividade foi publicada.",
        )
        cls.notificacao2 = Notificacao.objects.create(
            destinatario=cls.aluno2,
            atividade=cls.atividade2,
            tipo=Notificacao.Tipo.NOVA_ATIVIDADE,
            titulo="Aviso privado de outro aluno",
            mensagem="Mensagem privada de outro aluno.",
        )
        Progresso.objects.create(aluno=cls.aluno, xp_total=30)
        Progresso.objects.create(aluno=cls.aluno2, xp_total=90)

    def test_painel_exige_autenticacao(self):
        url = reverse("usuarios:painel")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('usuarios:login')}?next={url}",
        )

    def test_aluno_visualiza_somente_dados_das_suas_turmas(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/painel_aluno.html")
        self.assertEqual(response.context["disciplinas_total"], 1)
        self.assertEqual(response.context["atividades_total"], 1)
        self.assertEqual(response.context["nao_visualizadas"], 1)
        self.assertEqual(response.context["pontos"], 30)
        self.assertContains(response, self.disciplina.nome)
        self.assertContains(response, self.atividade.titulo)
        self.assertContains(response, self.notificacao.titulo)
        self.assertNotContains(response, self.disciplina2.nome)
        self.assertNotContains(response, self.atividade2.titulo)
        self.assertNotContains(response, self.notificacao2.titulo)
        self.assertQuerySetEqual(response.context["disciplinas"], [self.disciplina])
        self.assertQuerySetEqual(response.context["atividades"], [self.atividade])
        self.assertQuerySetEqual(response.context["notificacoes"], [self.notificacao])

    def test_professor_visualiza_somente_turmas_que_leciona(self):
        self.client.force_login(self.professor)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/painel_professor.html")
        self.assertEqual(response.context["disciplinas_total"], 1)
        self.assertEqual(response.context["atividades_total"], 1)
        self.assertEqual(response.context["alunos_total"], 1)
        self.assertQuerySetEqual(response.context["disciplinas"], [self.disciplina])
        self.assertQuerySetEqual(response.context["atividades"], [self.atividade])
        self.assertQuerySetEqual(response.context["notificacoes"], [])
        self.assertNotContains(response, self.disciplina2.nome)
        self.assertNotContains(response, self.atividade2.titulo)
        self.assertNotContains(response, self.notificacao.titulo)
        self.assertNotContains(response, self.notificacao2.titulo)

    def test_professor_conta_aluno_uma_vez_em_multiplas_turmas(self):
        disciplina = Disciplina.objects.create(nome="Algoritmos", professor=self.professor)
        disciplina.alunos.add(self.aluno)
        self.client.force_login(self.professor)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.context["disciplinas_total"], 2)
        self.assertEqual(response.context["alunos_total"], 1)

    def test_card_da_turma_conta_todos_os_alunos_matriculados(self):
        self.disciplina.alunos.add(self.aluno2)
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.context["disciplinas"][0].total_alunos, 2)

    def test_aluno_sem_dados_ve_painel_vazio_sem_criar_progresso(self):
        aluno = get_user_model().objects.create_user(username="novo", tipo="ALUNO")
        self.client.force_login(aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["disciplinas_total"], 0)
        self.assertEqual(response.context["atividades_total"], 0)
        self.assertEqual(response.context["nao_visualizadas"], 0)
        self.assertEqual(response.context["pontos"], 0)
        self.assertContains(response, "Você ainda não possui turmas")
        self.assertFalse(Progresso.objects.filter(aluno=aluno).exists())

    def test_aluno_removido_da_turma_nao_ve_seus_avisos_antigos(self):
        self.disciplina.alunos.remove(self.aluno)
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.context["nao_visualizadas"], 0)
        self.assertNotContains(response, self.notificacao.titulo)
        self.assertNotContains(response, self.atividade.titulo)

    def test_superusuario_sem_tipo_abre_painel_com_acesso_ao_admin(self):
        administrador = get_user_model().objects.create_superuser(username="admin")
        self.client.force_login(administrador)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/painel_professor.html")
        self.assertEqual(response.context["disciplinas_total"], 0)
        self.assertNotContains(response, self.disciplina.nome)
        self.assertContains(response, reverse("admin:index"))

    def test_aluno_com_acesso_ao_admin_continua_no_painel_de_aluno(self):
        self.aluno.is_staff = True
        self.aluno.save(update_fields=["is_staff"])
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertTemplateUsed(response, "usuarios/painel_aluno.html")
        self.assertEqual(response.context["pontos"], 30)

    def test_usuario_sem_tipo_e_sem_acesso_ao_admin_recebe_403(self):
        usuario = get_user_model().objects.create_user(username="sem_tipo")
        self.client.force_login(usuario)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertEqual(response.status_code, 403)

    def test_inicio_redireciona_usuario_autenticado_para_painel(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:inicio"))

        self.assertRedirects(response, reverse("usuarios:painel"))


class DisciplinaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.professor2 = Usuario.objects.create_user(username="professor2", tipo="PROFESSOR")
        cls.aluno = Usuario.objects.create_user(
            username="aluno", tipo="ALUNO", email="aluno@example.com",
        )
        cls.aluno2 = Usuario.objects.create_user(
            username="aluno2", tipo="ALUNO", email="colega@example.com",
        )
        cls.disciplina = Disciplina.objects.create(
            nome="Estrutura de Dados", professor=cls.professor,
        )
        cls.disciplina.alunos.add(cls.aluno, cls.aluno2)
        cls.disciplina2 = Disciplina.objects.create(
            nome="Outra turma", professor=cls.professor2,
        )
        cls.atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas",
            descricao="Implementar uma pilha em Python.",
            disciplina=cls.disciplina,
            prazo=timezone.now() + timedelta(days=3),
        )
        cls.atividade2 = Atividade.objects.create(
            titulo="Atividade de outra turma",
            disciplina=cls.disciplina2,
            prazo=timezone.now() + timedelta(days=3),
        )

    def test_listagem_e_detalhe_exigem_login(self):
        for url in [
            reverse("usuarios:disciplinas"),
            reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk}),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertRedirects(response, f"{reverse('usuarios:login')}?next={url}")

    def test_listagem_mostra_apenas_turmas_do_usuario(self):
        for usuario in [self.aluno, self.professor]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                response = self.client.get(reverse("usuarios:disciplinas"))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "usuarios/disciplinas.html")
                self.assertQuerySetEqual(response.context["disciplinas"], [self.disciplina])
                self.assertEqual(response.context["disciplinas"][0].total_alunos, 2)
                self.assertContains(response, self.disciplina.nome)
                self.assertNotContains(response, self.disciplina2.nome)
                self.assertContains(
                    response,
                    reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk}),
                )

    def test_aluno_consulta_atividades_sem_ver_dados_dos_colegas(self):
        self.client.force_login(self.aluno)
        url = reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/detalhe_disciplina.html")
        self.assertContains(response, self.atividade.titulo)
        self.assertContains(response, self.atividade.descricao)
        self.assertNotContains(response, self.atividade2.titulo)
        self.assertFalse(response.context["pode_ver_alunos"])
        self.assertQuerySetEqual(response.context["alunos"], [])
        self.assertNotContains(response, self.aluno2.email)

    def test_professor_consulta_alunos_e_atividades_da_sua_turma(self):
        self.client.force_login(self.professor)
        url = reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["pode_ver_alunos"])
        self.assertQuerySetEqual(response.context["alunos"], [self.aluno, self.aluno2])
        self.assertContains(response, self.aluno.email)
        self.assertContains(response, self.aluno2.email)
        self.assertQuerySetEqual(response.context["atividades"], [self.atividade])

    def test_detalhe_bloqueia_usuarios_sem_vinculo_com_a_turma(self):
        externo = get_user_model().objects.create_user(username="externo", tipo="ALUNO")
        administrador = get_user_model().objects.create_superuser(username="admin")
        url = reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk})

        for usuario in [externo, self.professor2, administrador]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                response = self.client.get(url)

                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, self.atividade.descricao, status_code=404)

    def test_aluno_removido_perde_acesso_a_listagem_e_detalhe(self):
        self.disciplina.alunos.remove(self.aluno)
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:disciplinas"))

        self.assertQuerySetEqual(response.context["disciplinas"], [])
        response = self.client.get(
            reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk}),
        )
        self.assertEqual(response.status_code, 404)

    def test_disciplina_inexistente_retorna_404(self):
        self.client.force_login(self.aluno)
        url = reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina2.pk + 1000})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_listagem_completa_nao_tem_limite_de_seis_turmas(self):
        for indice in range(7):
            disciplina = Disciplina.objects.create(
                nome=f"Algoritmos {indice}", professor=self.professor,
            )
            disciplina.alunos.add(self.aluno)
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:disciplinas"))

        self.assertEqual(len(response.context["disciplinas"]), 8)
        nomes = [disciplina.nome for disciplina in response.context["disciplinas"]]
        self.assertEqual(nomes, sorted(nomes))

    def test_turma_sem_atividades_ou_alunos_exibe_estado_vazio(self):
        self.client.force_login(self.professor2)
        self.atividade2.delete()

        response = self.client.get(
            reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina2.pk}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhuma atividade cadastrada nesta turma.")
        self.assertContains(response, "Ainda não há alunos matriculados nesta disciplina.")


class GerenciarDisciplinaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.professor2 = Usuario.objects.create_user(username="professor2", tipo="PROFESSOR")
        cls.aluno = Usuario.objects.create_user(username="aluno", tipo="ALUNO")
        cls.aluno2 = Usuario.objects.create_user(username="aluno2", tipo="ALUNO")
        cls.disciplina = Disciplina.objects.create(nome="Estrutura de Dados", professor=cls.professor)
        cls.disciplina.alunos.add(cls.aluno)
        cls.atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas", disciplina=cls.disciplina,
            prazo=timezone.now() + timedelta(days=1),
        )

    def setUp(self):
        self.url_criar = reverse("usuarios:criar_disciplina")
        self.url_editar = reverse(
            "usuarios:editar_disciplina", kwargs={"disciplina_id": self.disciplina.pk},
        )

    def test_criacao_e_edicao_exigem_login(self):
        for url in [self.url_criar, self.url_editar]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('usuarios:login')}?next={url}")

    def test_apenas_professores_podem_gerenciar_turmas(self):
        administrador = get_user_model().objects.create_superuser(username="admin")
        self.aluno.is_staff = True
        self.aluno.save(update_fields=["is_staff"])
        for usuario in [self.aluno, administrador]:
            self.client.force_login(usuario)
            for url in [self.url_criar, self.url_editar]:
                for metodo in [self.client.get, self.client.post]:
                    with self.subTest(usuario=usuario.username, url=url, metodo=metodo.__name__):
                        response = metodo(url)
                        self.assertEqual(response.status_code, 403)
        self.assertEqual(Disciplina.objects.count(), 1)

    def test_formulario_oferece_somente_alunos(self):
        self.client.force_login(self.professor)
        response = self.client.get(self.url_criar)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usuarios/form_disciplina.html")
        self.assertQuerySetEqual(
            response.context["form"].fields["alunos"].queryset,
            [self.aluno, self.aluno2],
        )
        self.assertNotIn("professor", response.context["form"].fields)
        self.assertContains(response, 'type="checkbox"')

    def test_professor_cria_disciplina_com_matriculas_e_ignora_professor_enviado(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url_criar, data={
            "nome": "Algoritmos",
            "alunos": [self.aluno.pk, self.aluno2.pk],
            "professor": self.professor2.pk,
        })

        disciplina = Disciplina.objects.get(nome="Algoritmos")
        self.assertRedirects(response, reverse(
            "usuarios:detalhe_disciplina", kwargs={"disciplina_id": disciplina.pk},
        ))
        self.assertEqual(disciplina.professor, self.professor)
        self.assertCountEqual(disciplina.alunos.all(), [self.aluno, self.aluno2])

    def test_professor_cria_turma_sem_alunos(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url_criar, data={"nome": "Turma nova"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Disciplina.objects.get(nome="Turma nova").alunos.exists())

    def test_nome_vazio_e_participante_que_nao_e_aluno_sao_rejeitados(self):
        self.client.force_login(self.professor)
        for dados, campo in [
            ({"nome": "   "}, "nome"),
            ({"nome": "Algoritmos", "alunos": [self.professor2.pk]}, "alunos"),
        ]:
            with self.subTest(campo=campo):
                response = self.client.post(self.url_criar, data=dados)
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
                self.assertEqual(Disciplina.objects.count(), 1)

    def test_edicao_carrega_dados_e_matriculas_atuais(self):
        self.client.force_login(self.professor)

        response = self.client.get(self.url_editar)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["nome"], self.disciplina.nome)
        self.assertEqual(response.context["form"]["alunos"].value(), [self.aluno.pk])

    def test_professor_nao_edita_turma_de_outro_professor(self):
        self.client.force_login(self.professor2)
        for metodo in [self.client.get, self.client.post]:
            with self.subTest(metodo=metodo.__name__):
                response = metodo(self.url_editar, data={"nome": "Alterado"})
                self.assertEqual(response.status_code, 404)
        self.disciplina.refresh_from_db()
        self.assertEqual(self.disciplina.nome, "Estrutura de Dados")
        self.assertCountEqual(self.disciplina.alunos.all(), [self.aluno])

    def test_edicao_atualiza_nome_e_matriculas_sem_trocar_professor(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url_editar, data={
            "nome": "Algoritmos", "alunos": [self.aluno2.pk],
            "professor": self.professor2.pk,
        })

        self.assertEqual(response.status_code, 302)
        self.disciplina.refresh_from_db()
        self.assertEqual(self.disciplina.nome, "Algoritmos")
        self.assertEqual(self.disciplina.professor, self.professor)
        self.assertCountEqual(self.disciplina.alunos.all(), [self.aluno2])

    def test_novo_aluno_recebe_avisos_sem_alterar_notificacao_existente(self):
        criar_notificacoes_da_atividade(self.atividade)
        existente = Notificacao.objects.get(destinatario=self.aluno)
        existente.visualizada = True
        existente.visualizada_em = timezone.now()
        existente.save(update_fields=["visualizada", "visualizada_em"])
        self.client.force_login(self.professor)
        dados = {"nome": self.disciplina.nome, "alunos": [self.aluno.pk, self.aluno2.pk]}

        response = self.client.post(self.url_editar, data=dados)
        repetida = self.client.post(self.url_editar, data=dados)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(repetida.status_code, 302)
        self.assertEqual(Notificacao.objects.count(), 2)
        nova = Notificacao.objects.get(destinatario=self.aluno2)
        self.assertEqual(nova.atividade, self.atividade)
        self.assertEqual(nova.prioridade, Notificacao.Prioridade.URGENTE)
        self.assertFalse(nova.visualizada)
        self.assertIsNone(nova.visualizada_em)
        data_original = existente.visualizada_em
        existente.refresh_from_db()
        self.assertTrue(existente.visualizada)
        self.assertEqual(existente.visualizada_em, data_original)
        self.assertFalse(Progresso.objects.exists())

    def test_rematricula_reutiliza_aviso_anterior(self):
        criar_notificacoes_da_atividade(self.atividade)
        original = Notificacao.objects.get(destinatario=self.aluno)
        self.client.force_login(self.professor)

        self.client.post(self.url_editar, data={"nome": self.disciplina.nome})
        response = self.client.post(self.url_editar, data={
            "nome": self.disciplina.nome, "alunos": [self.aluno.pk],
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notificacao.objects.count(), 1)
        self.assertEqual(Notificacao.objects.get().pk, original.pk)

    def test_formulario_invalido_nao_altera_turma_ou_matriculas(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url_editar, data={
            "nome": "", "alunos": [self.aluno2.pk],
        })

        self.assertEqual(response.status_code, 200)
        self.disciplina.refresh_from_db()
        self.assertEqual(self.disciplina.nome, "Estrutura de Dados")
        self.assertCountEqual(self.disciplina.alunos.all(), [self.aluno])
        self.assertFalse(Notificacao.objects.exists())

    def test_falha_nos_avisos_desfaz_edicao_e_matriculas(self):
        self.client.force_login(self.professor)

        def criar_aviso_e_falhar(atividade, alunos):
            criar_notificacoes_da_atividade(atividade, alunos=alunos)
            raise RuntimeError("Falha após criar aviso")

        with patch(
            "usuarios.views.criar_notificacoes_da_atividade",
            side_effect=criar_aviso_e_falhar,
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url_editar, data={
                    "nome": "Nome alterado", "alunos": [self.aluno2.pk],
                })

        self.disciplina.refresh_from_db()
        self.assertEqual(self.disciplina.nome, "Estrutura de Dados")
        self.assertCountEqual(self.disciplina.alunos.all(), [self.aluno])
        self.assertFalse(Notificacao.objects.exists())

    def test_criacao_e_edicao_sem_csrf_sao_bloqueadas(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.professor)
        for url in [self.url_criar, self.url_editar]:
            with self.subTest(url=url):
                response = cliente.post(url, data={"nome": "Tentativa"})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(Disciplina.objects.count(), 1)
        self.disciplina.refresh_from_db()
        self.assertEqual(self.disciplina.nome, "Estrutura de Dados")

    def test_servico_de_avisos_filtra_alunos_e_preserva_chamada_original(self):
        externo = get_user_model().objects.create_user(username="externo", tipo="ALUNO")

        criar_notificacoes_da_atividade(self.atividade, alunos=[])
        criar_notificacoes_da_atividade(self.atividade, alunos=[externo])

        self.assertFalse(Notificacao.objects.exists())

        criar_notificacoes_da_atividade(self.atividade)

        self.assertEqual(Notificacao.objects.count(), 1)
        self.assertEqual(Notificacao.objects.get().destinatario, self.aluno)
