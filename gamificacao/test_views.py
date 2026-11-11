from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from atividades.models import Atividade, Disciplina
from notificacoes.models import Notificacao

from .models import EventoXP, Progresso


class RankingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.professor = Usuario.objects.create_user(username="professor", tipo="PROFESSOR")
        cls.lider = Usuario.objects.create_user(username="ana", tipo="ALUNO")
        cls.aluno = Usuario.objects.create_user(username="maria", tipo="ALUNO")
        cls.sem_progresso = Usuario.objects.create_user(username="bia", tipo="ALUNO")
        cls.inativo = Usuario.objects.create_user(username="inativo", tipo="ALUNO", is_active=False)
        Progresso.objects.create(aluno=cls.lider, xp_total=15)
        Progresso.objects.create(aluno=cls.aluno, xp_total=10)
        Progresso.objects.create(aluno=cls.inativo, xp_total=999)

    def setUp(self):
        self.url = reverse("gamificacao:ranking")

    def test_ranking_exige_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(response, f"{reverse('usuarios:login')}?next={self.url}")

    def test_ranking_ordena_alunos_ativos_por_xp_e_inclui_zero(self):
        self.client.force_login(self.aluno)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gamificacao/ranking.html")
        alunos = list(response.context["alunos"])
        self.assertEqual([aluno.pk for aluno in alunos], [self.lider.pk, self.aluno.pk, self.sem_progresso.pk])
        self.assertEqual([aluno.total_pontos for aluno in alunos], [15, 10, 0])
        self.assertEqual(response.context["meus_pontos"], 10)
        self.assertContains(response, 'aria-current="true"')
        self.assertNotContains(response, self.inativo.username)
        self.assertNotIn(self.professor.pk, [aluno.pk for aluno in alunos])

    def test_ranking_nao_cria_progresso_ou_concede_xp(self):
        self.client.force_login(self.sem_progresso)
        quantidade = Progresso.objects.count()

        response = self.client.get(self.url)

        self.assertEqual(response.context["meus_pontos"], 0)
        self.assertEqual(Progresso.objects.count(), quantidade)
        self.assertFalse(Progresso.objects.filter(aluno=self.sem_progresso).exists())
        self.assertFalse(EventoXP.objects.exists())

    def test_professor_consulta_ranking_sem_aparecer_como_aluno(self):
        self.client.force_login(self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["meus_pontos"])
        self.assertNotContains(response, "Seu XP")
        self.assertEqual(len(response.context["alunos"]), 3)

    def test_empates_tem_ordem_deterministica_por_nome_e_usuario(self):
        Progresso.objects.filter(aluno=self.lider).update(xp_total=10)
        self.client.force_login(self.professor)

        response = self.client.get(self.url)

        self.assertEqual([aluno.username for aluno in response.context["alunos"]], ["ana", "maria", "bia"])

    def test_limite_de_vinte_nao_oculta_xp_pessoal(self):
        for indice in range(21):
            aluno = get_user_model().objects.create_user(username=f"destaque{indice}", tipo="ALUNO")
            Progresso.objects.create(aluno=aluno, xp_total=100 + indice)
        self.client.force_login(self.aluno)

        response = self.client.get(self.url)

        alunos = list(response.context["alunos"])
        self.assertEqual(len(alunos), 20)
        self.assertNotIn(self.aluno.pk, [aluno.pk for aluno in alunos])
        self.assertEqual(response.context["meus_pontos"], 10)
        self.assertEqual(alunos[0].total_pontos, 120)

    def test_sem_alunos_ativos_exibe_estado_vazio(self):
        get_user_model().objects.filter(tipo="ALUNO").update(is_active=False)
        self.client.force_login(self.professor)

        response = self.client.get(self.url)

        self.assertContains(response, "Nenhum aluno ativo cadastrado ainda.")
        self.assertQuerySetEqual(response.context["alunos"], [])

    def test_visualizar_aviso_importante_atualiza_ranking_sem_duplicar_xp(self):
        disciplina = Disciplina.objects.create(nome="Estrutura de Dados", professor=self.professor)
        disciplina.alunos.add(self.aluno)
        atividade = Atividade.objects.create(
            titulo="Trabalho de Pilhas", disciplina=disciplina,
            prazo=timezone.now() + timedelta(hours=36),
        )
        aviso = Notificacao.objects.create(
            destinatario=self.aluno, atividade=atividade, tipo=Notificacao.Tipo.NOVA_ATIVIDADE,
            prioridade=Notificacao.Prioridade.IMPORTANTE, titulo="Nova atividade", mensagem="Confira a atividade.",
        )
        self.client.force_login(self.aluno)
        url_aviso = reverse("notificacoes:visualizar_notificacao", kwargs={"notificacao_id": aviso.pk})

        self.assertEqual(self.client.post(url_aviso, HTTP_ACCEPT="application/json").status_code, 200)
        self.assertEqual(self.client.post(url_aviso, HTTP_ACCEPT="application/json").status_code, 200)
        response = self.client.get(self.url)

        self.assertEqual(response.context["meus_pontos"], 20)
        self.assertEqual(response.context["alunos"][0].pk, self.aluno.pk)
        self.assertEqual(EventoXP.objects.count(), 1)

    def test_menu_e_painel_do_aluno_tem_link_para_ranking(self):
        self.client.force_login(self.aluno)

        response = self.client.get(reverse("usuarios:painel"))

        self.assertContains(response, f'href="{self.url}"', count=2)
