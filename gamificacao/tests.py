from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import EventoXP, Progresso
from .services import conceder_xp


class ConcederXPTests(TestCase):
    def setUp(self):
        Usuario = get_user_model()
        self.aluno = Usuario.objects.create_user(
            username="aluno_teste",
            password="senha-de-teste",
            tipo="ALUNO",
        )
        self.professor = Usuario.objects.create_user(
            username="professor_teste",
            password="senha-de-teste",
            tipo="PROFESSOR",
        )

    def test_primeira_recompensa_cria_progresso_evento_e_soma_xp(self):
        evento, criado = conceder_xp(
            aluno=self.aluno,
            codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
            referencia_id=42,
            quantidade=10,
        )

        self.assertTrue(criado)
        self.assertEqual(evento.quantidade, 10)
        self.assertEqual(EventoXP.objects.count(), 1)

        progresso = Progresso.objects.get(aluno=self.aluno)
        self.assertEqual(progresso.xp_total, 10)

    def test_mesma_origem_nao_concede_xp_uma_segunda_vez(self):
        primeira, criado_na_primeira = conceder_xp(
            aluno=self.aluno,
            codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
            referencia_id=42,
            quantidade=10,
        )
        segunda, criado_na_segunda = conceder_xp(
            aluno=self.aluno,
            codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
            referencia_id=42,
            quantidade=10,
        )

        self.assertTrue(criado_na_primeira)
        self.assertFalse(criado_na_segunda)
        self.assertEqual(primeira.pk, segunda.pk)
        self.assertEqual(Progresso.objects.get(aluno=self.aluno).xp_total, 10)
        self.assertEqual(EventoXP.objects.count(), 1)

    def test_outra_referencia_pode_conceder_nova_recompensa(self):
        for referencia in (42, 43):
            conceder_xp(
                aluno=self.aluno,
                codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
                referencia_id=referencia,
                quantidade=10,
            )

        self.assertEqual(Progresso.objects.get(aluno=self.aluno).xp_total, 20)
        self.assertEqual(EventoXP.objects.count(), 2)

    def test_professor_nao_recebe_xp(self):
        with self.assertRaises(ValidationError):
            conceder_xp(
                aluno=self.professor,
                codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
                referencia_id=42,
                quantidade=10,
            )

        self.assertFalse(Progresso.objects.filter(aluno=self.professor).exists())

    def test_codigo_invalido_e_rejeitado(self):
        with self.assertRaises(ValidationError):
            conceder_xp(
                aluno=self.aluno,
                codigo="CODIGO_QUE_NAO_EXISTE",
                referencia_id=42,
                quantidade=10,
            )

    def test_quantidade_zero_ou_negativa_e_rejeitada(self):
        for quantidade in (0, -5):
            with self.subTest(quantidade=quantidade):
                with self.assertRaises(ValidationError):
                    conceder_xp(
                        aluno=self.aluno,
                        codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
                        referencia_id=42,
                        quantidade=quantidade,
                    )

        self.assertFalse(Progresso.objects.filter(aluno=self.aluno).exists())

    def test_referencia_invalida_e_rejeitada(self):
        for referencia in (0, -1, True):
            with self.subTest(referencia=referencia):
                with self.assertRaises(ValidationError):
                    conceder_xp(
                        aluno=self.aluno,
                        codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
                        referencia_id=referencia,
                        quantidade=10,
                    )

    def test_banco_impede_evento_duplicado_mesmo_fora_do_service(self):
        evento, _ = conceder_xp(
            aluno=self.aluno,
            codigo=EventoXP.Codigo.NOTIFICACAO_IMPORTANTE_VISUALIZADA,
            referencia_id=42,
            quantidade=10,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventoXP.objects.create(
                    progresso=evento.progresso,
                    codigo=evento.codigo,
                    referencia_id=evento.referencia_id,
                    quantidade=10,
                )

    def test_banco_impede_quantidade_zero(self):
        progresso = Progresso.objects.create(aluno=self.aluno)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventoXP.objects.create(
                    progresso=progresso,
                    codigo=EventoXP.Codigo.MISSAO_CONCLUIDA,
                    referencia_id=100,
                    quantidade=0,
                )
