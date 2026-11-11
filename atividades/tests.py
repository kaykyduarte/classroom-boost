from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from gamificacao.models import EventoXP, Progresso
from notificacoes.models import Notificacao
from notificacoes.services import criar_notificacoes_da_atividade

from .models import Atividade, Disciplina


class AtividadeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.professor2 = Usuario.objects.create_user(username="professor2", tipo="PROFESSOR")
        cls.aluno = Usuario.objects.create_user(username="aluno", tipo="ALUNO")
        cls.aluno2 = Usuario.objects.create_user(username="aluno2", tipo="ALUNO")
        cls.disciplina = Disciplina.objects.create(nome="Estrutura de Dados", professor=cls.professor)
        cls.disciplina.alunos.add(cls.aluno)
        cls.disciplina2 = Disciplina.objects.create(nome="Outra turma", professor=cls.professor2)
        cls.disciplina2.alunos.add(cls.aluno2)
        prazo = timezone.now() + timedelta(days=3)
        cls.atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas", descricao="Implementar uma pilha em Python.",
            disciplina=cls.disciplina, prazo=prazo,
        )
        cls.atividade_antecipada = Atividade.objects.create(
            titulo="Trabalho de Filas", disciplina=cls.disciplina, prazo=prazo - timedelta(days=1),
        )
        cls.atividade2 = Atividade.objects.create(
            titulo="Atividade privada de outra turma", descricao="Orientações de outra turma.",
            disciplina=cls.disciplina2, prazo=prazo,
        )

    def setUp(self):
        self.url_lista = reverse("atividades:lista")
        self.url_detalhe = reverse("atividades:detalhe", kwargs={"atividade_id": self.atividade.pk})

    def test_listagem_e_detalhe_exigem_login(self):
        for url in [self.url_lista, self.url_detalhe]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('usuarios:login')}?next={url}")

    def test_listagem_mostra_atividades_permitidas_em_ordem_de_prazo(self):
        for usuario in [self.aluno, self.professor]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                response = self.client.get(self.url_lista)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "atividades/lista.html")
                self.assertQuerySetEqual(
                    response.context["atividades"], [self.atividade_antecipada, self.atividade],
                )
                self.assertContains(response, self.url_detalhe)
                self.assertNotContains(response, self.atividade2.titulo)
                self.assertNotContains(response, self.disciplina2.nome)

    def test_participantes_consultam_detalhe_e_link_da_disciplina(self):
        for usuario in [self.aluno, self.professor]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                response = self.client.get(self.url_detalhe)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "atividades/detalhe.html")
                self.assertEqual(response.context["atividade"], self.atividade)
                self.assertContains(response, self.atividade.descricao)
                self.assertContains(response, reverse(
                    "usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk},
                ))

    def test_usuario_sem_vinculo_recebe_404_no_detalhe(self):
        administrador = get_user_model().objects.create_superuser(username="admin")
        for usuario in [self.aluno2, self.professor2, administrador]:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)

                response = self.client.get(self.url_detalhe)

                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, self.atividade.descricao, status_code=404)

    def test_aluno_removido_da_turma_perde_acesso(self):
        self.disciplina.alunos.remove(self.aluno)
        self.client.force_login(self.aluno)

        response = self.client.get(self.url_lista)

        self.assertQuerySetEqual(response.context["atividades"], [])
        self.assertEqual(self.client.get(self.url_detalhe).status_code, 404)

    def test_atividade_inexistente_retorna_404(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse(
            "atividades:detalhe", kwargs={"atividade_id": self.atividade2.pk + 1000},
        ))

        self.assertEqual(response.status_code, 404)

    def test_usuario_sem_perfil_recebe_403(self):
        usuario = get_user_model().objects.create_user(username="sem_tipo")
        self.client.force_login(usuario)
        for url in [self.url_lista, self.url_detalhe]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_aluno_com_acesso_ao_admin_continua_limitado_as_suas_turmas(self):
        self.aluno.is_staff = True
        self.aluno.save(update_fields=["is_staff"])
        self.client.force_login(self.aluno)

        response = self.client.get(self.url_lista)

        self.assertNotContains(response, self.atividade2.titulo)
        self.assertEqual(self.client.get(reverse(
            "atividades:detalhe", kwargs={"atividade_id": self.atividade2.pk},
        )).status_code, 404)

    def test_usuario_sem_atividades_ve_lista_vazia(self):
        aluno = get_user_model().objects.create_user(username="novo", tipo="ALUNO")
        self.client.force_login(aluno)

        response = self.client.get(self.url_lista)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhuma atividade publicada nas suas turmas.")

    def test_detalhe_sem_descricao_exibe_texto_padrao(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse(
            "atividades:detalhe", kwargs={"atividade_id": self.atividade_antecipada.pk},
        ))

        self.assertContains(response, "Nenhuma descrição adicional.")

    def test_descricao_preserva_quebras_de_linha_e_escapa_html(self):
        self.atividade.descricao = 'Primeira linha\n<script>alert("teste")</script>'
        self.atividade.save(update_fields=["descricao"])
        self.client.force_login(self.aluno)

        response = self.client.get(self.url_detalhe)

        self.assertContains(response, "Primeira linha<br>")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("teste")</script>')

    def test_painel_e_disciplina_tem_links_para_detalhe_da_atividade(self):
        self.client.force_login(self.aluno)
        for url in [
            reverse("usuarios:painel"),
            reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk}),
        ]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), f'href="{self.url_detalhe}"')


class CriarAtividadeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.professor2 = Usuario.objects.create_user(username="professor2", tipo="PROFESSOR")
        cls.aluno = Usuario.objects.create_user(username="aluno", tipo="ALUNO")
        cls.aluno2 = Usuario.objects.create_user(username="aluno2", tipo="ALUNO")
        cls.externo = Usuario.objects.create_user(username="externo", tipo="ALUNO")
        cls.disciplina = Disciplina.objects.create(nome="Estrutura de Dados", professor=cls.professor)
        cls.disciplina.alunos.add(cls.aluno, cls.aluno2)
        cls.disciplina2 = Disciplina.objects.create(nome="Outra turma", professor=cls.professor2)

    def setUp(self):
        self.url = reverse("atividades:criar")
        self.dados = {
            "titulo": "Trabalho de Pilhas",
            "descricao": "Implementar uma pilha em Python.",
            "disciplina": self.disciplina.pk,
            "prazo": timezone.localtime(timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
        }

    def test_publicacao_exige_login(self):
        response = self.client.post(self.url, data=self.dados)

        self.assertRedirects(response, f"{reverse('usuarios:login')}?next={self.url}")
        self.assertFalse(Atividade.objects.exists())

    def test_apenas_professores_podem_publicar(self):
        administrador = get_user_model().objects.create_superuser(username="admin")
        self.aluno.is_staff = True
        self.aluno.save(update_fields=["is_staff"])
        for usuario in [self.aluno, administrador]:
            self.client.force_login(usuario)
            for metodo in [self.client.get, self.client.post]:
                with self.subTest(usuario=usuario.username, metodo=metodo.__name__):
                    response = metodo(self.url, data=self.dados)
                    self.assertEqual(response.status_code, 403)
        self.assertFalse(Atividade.objects.exists())
        self.assertFalse(Notificacao.objects.exists())

    def test_formulario_lista_somente_disciplinas_do_professor(self):
        self.client.force_login(self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "atividades/form_atividade.html")
        self.assertQuerySetEqual(response.context["form"].fields["disciplina"].queryset, [self.disciplina])
        self.assertContains(response, 'type="datetime-local"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertFalse(Atividade.objects.exists())

    def test_publicacao_persiste_atividade_e_notifica_apenas_matriculados(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url, data=self.dados, follow=True)

        self.assertEqual(Atividade.objects.count(), 1)
        atividade = Atividade.objects.get()
        self.assertRedirects(response, reverse("atividades:detalhe", kwargs={"atividade_id": atividade.pk}))
        self.assertEqual(atividade.titulo, self.dados["titulo"])
        self.assertEqual(atividade.descricao, self.dados["descricao"])
        self.assertEqual(atividade.disciplina, self.disciplina)
        self.assertTrue(timezone.is_aware(atividade.prazo))
        self.assertEqual(timezone.localtime(atividade.prazo).strftime("%Y-%m-%dT%H:%M"), self.dados["prazo"])
        self.assertContains(response, "Atividade publicada.")
        self.assertCountEqual(
            Notificacao.objects.filter(atividade=atividade).values_list("destinatario_id", flat=True),
            [self.aluno.pk, self.aluno2.pk],
        )
        self.assertFalse(Notificacao.objects.filter(destinatario=self.externo).exists())
        self.assertFalse(EventoXP.objects.exists())
        self.assertFalse(Progresso.objects.exists())

    def test_prioridade_dos_avisos_depende_do_prazo(self):
        self.client.force_login(self.professor)
        for horas, prioridade in [
            (12, Notificacao.Prioridade.URGENTE),
            (36, Notificacao.Prioridade.IMPORTANTE),
            (72, Notificacao.Prioridade.NORMAL),
        ]:
            with self.subTest(horas=horas):
                prazo = timezone.localtime(timezone.now() + timedelta(hours=horas))
                response = self.client.post(self.url, data={
                    **self.dados, "titulo": f"Atividade {horas}",
                    "prazo": prazo.strftime("%Y-%m-%dT%H:%M"),
                })
                self.assertEqual(response.status_code, 302)
                atividade = Atividade.objects.get(titulo=f"Atividade {horas}")
                avisos = Notificacao.objects.filter(atividade=atividade)
                self.assertEqual(avisos.count(), 2)
                self.assertTrue(all(aviso.prioridade == prioridade for aviso in avisos))
                self.assertFalse(avisos.filter(visualizada=True).exists())

    def test_professor_nao_publica_em_disciplina_de_outro(self):
        self.client.force_login(self.professor)

        response = self.client.post(self.url, data={**self.dados, "disciplina": self.disciplina2.pk})

        self.assertEqual(response.status_code, 200)
        self.assertIn("disciplina", response.context["form"].errors)
        self.assertFalse(Atividade.objects.exists())
        self.assertFalse(Notificacao.objects.exists())

    def test_dados_invalidos_nao_criam_atividade_nem_avisos(self):
        self.client.force_login(self.professor)
        passado = timezone.localtime(timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        for campo, valor in [
            ("titulo", "   "), ("prazo", ""), ("prazo", "invalido"), ("prazo", passado),
        ]:
            with self.subTest(campo=campo, valor=valor):
                response = self.client.post(self.url, data={**self.dados, campo: valor})
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
                self.assertFalse(Atividade.objects.exists())
                self.assertFalse(Notificacao.objects.exists())

    def test_turma_sem_alunos_aceita_atividade_sem_descricao(self):
        self.disciplina.alunos.clear()
        self.client.force_login(self.professor)

        response = self.client.post(self.url, data={**self.dados, "descricao": ""})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Atividade.objects.get().descricao, "")
        self.assertFalse(Notificacao.objects.exists())

    def test_sem_disciplinas_exibe_link_para_criar_turma(self):
        professor = get_user_model().objects.create_user(username="novo", tipo="PROFESSOR")
        self.client.force_login(professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Você precisa criar uma disciplina")
        self.assertContains(response, reverse("usuarios:criar_disciplina"))
        self.assertFalse(Atividade.objects.exists())

    def test_link_da_turma_preseleciona_disciplina(self):
        self.client.force_login(self.professor)

        response = self.client.get(self.url, data={"disciplina": self.disciplina.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["disciplina"].value(), self.disciplina.pk)

    def test_disciplina_invalida_ou_de_outro_professor_na_url_retorna_404(self):
        self.client.force_login(self.professor)
        for disciplina in ["invalida", self.disciplina2.pk, self.disciplina2.pk + 1000]:
            with self.subTest(disciplina=disciplina):
                response = self.client.get(self.url, data={"disciplina": disciplina})
                self.assertEqual(response.status_code, 404)

    def test_falha_nas_notificacoes_desfaz_publicacao(self):
        self.client.force_login(self.professor)

        def criar_avisos_e_falhar(atividade):
            criar_notificacoes_da_atividade(atividade)
            raise RuntimeError("Falha após criar avisos")

        with patch("atividades.views.criar_notificacoes_da_atividade", side_effect=criar_avisos_e_falhar):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, data=self.dados)

        self.assertFalse(Atividade.objects.exists())
        self.assertFalse(Notificacao.objects.exists())

    def test_publicacao_sem_csrf_e_bloqueada(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.professor)

        response = cliente.post(self.url, data=self.dados)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Atividade.objects.exists())
        self.assertFalse(Notificacao.objects.exists())

    def test_outros_metodos_http_nao_publicam(self):
        self.client.force_login(self.professor)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(Atividade.objects.exists())

    def test_botoes_de_publicacao_aparecem_apenas_para_professor(self):
        urls = [
            reverse("atividades:lista"), reverse("usuarios:painel"),
            reverse("usuarios:detalhe_disciplina", kwargs={"disciplina_id": self.disciplina.pk}),
        ]
        for usuario in [self.professor, self.aluno]:
            self.client.force_login(usuario)
            for url in urls:
                with self.subTest(usuario=usuario.username, url=url):
                    response = self.client.get(url)
                    if usuario == self.professor:
                        self.assertContains(response, f'href="{self.url}')
                    else:
                        self.assertNotContains(response, f'href="{self.url}')
