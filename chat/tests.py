from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from atividades.models import Disciplina

from .models import Conversa, Mensagem
from .services import (
    ConversaInvalidaError,
    MensagemInvalidaError,
    criar_ou_obter_conversa,
    enviar_mensagem,
    listar_mensagens,
)

# Create your tests here.

Usuario = get_user_model()

class ConversaServiceTests(TestCase):
    def setUp(self):
        self.professor = Usuario.objects.create_user(
            username="professor",
            password="senha-teste",
            tipo=Usuario.Tipo.PROFESSOR,
        )

        self.professor2 = Usuario.objects.create_user(
            username="professor2",
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

        self.disciplina.alunos.add(self.aluno1)    

    def test_cria_conversa_para_aluno_matriculado(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        self.assertEqual(Conversa.objects.count(), 1)
        self.assertEqual(conversa.aluno, self.aluno1)
        self.assertEqual(conversa.professor, self.professor)
        self.assertEqual(conversa.disciplina, self.disciplina)

    def test_reutiliza_conversa_existente(self):
        primeira_conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        segunda_conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        self.assertEqual(primeira_conversa.pk, segunda_conversa.pk)
        self.assertEqual(Conversa.objects.count(), 1)

    def test_rejeita_aluno_nao_matriculado(self):
        with self.assertRaises(ConversaInvalidaError):
            criar_ou_obter_conversa(
                aluno=self.aluno2,
                professor=self.professor,
                disciplina=self.disciplina,
            )

        self.assertEqual(Conversa.objects.count(), 0)

    def test_rejeita_professor_nao_responsavel(self):
        with self.assertRaisesRegex(
            ConversaInvalidaError,
            "O professor informado não é responsável pela disciplina.",
        ):
            criar_ou_obter_conversa(
                aluno=self.aluno1,
                professor=self.professor2,
                disciplina=self.disciplina,
            )

        self.assertEqual(Conversa.objects.count(), 0)

    def test_rejeita_professor_informado_como_aluno(self):
        with self.assertRaisesRegex(
            ConversaInvalidaError,
            "deve possuir o tipo ALUNO",
        ):
            criar_ou_obter_conversa(
                aluno=self.professor2,
                professor=self.professor,
                disciplina=self.disciplina,
            )

        self.assertEqual(Conversa.objects.count(), 0)

    def test_rejeita_aluno_informado_como_professor(self):
        with self.assertRaisesRegex(
            ConversaInvalidaError,
            "deve possuir o tipo PROFESSOR",
        ):
            criar_ou_obter_conversa(
                aluno=self.aluno1,
                professor=self.aluno2,
                disciplina=self.disciplina,
            )

        self.assertEqual(Conversa.objects.count(), 0)

    def test_aluno_envia_mensagem_valida(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno1,
            conteudo="Olá, professor!",
        )

        self.assertEqual(Mensagem.objects.count(), 1)
        self.assertEqual(mensagem.conversa, conversa)
        self.assertEqual(mensagem.remetente, self.aluno1)
        self.assertEqual(mensagem.conteudo, "Olá, professor!")

    def test_rejeita_mensagem_de_usuario_nao_participante(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        with self.assertRaisesRegex(
            MensagemInvalidaError,
            "O remetente deve ser um dos participantes da conversa",
        ):
            enviar_mensagem(
                conversa=conversa,
                remetente=self.aluno2,
                conteudo="Olá, professor!",
            )

        self.assertEqual(Mensagem.objects.count(), 0)             

    def test_rejeita_mensagem_apenas_com_espacos(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        with self.assertRaisesRegex(
            MensagemInvalidaError,
            "O conteúdo da mensagem não pode estar vazio",
        ):
            enviar_mensagem(
                conversa=conversa,
                remetente=self.aluno1,
                conteudo="     ",
            )

        self.assertEqual(Mensagem.objects.count(), 0)

    def test_remove_espacos_externos_da_mensagem(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno1,
            conteudo="    Ola, professor!     ",
        )

        self.assertEqual(mensagem.conteudo, "Ola, professor!")

        mensagem.refresh_from_db()

        self.assertEqual(mensagem.conteudo, "Ola, professor!")

    def test_professor_envia_mensagem_valida(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=self.professor,
            conteudo="Bom Dia, aluno!",
        )

        self.assertEqual(Mensagem.objects.count(), 1)
        self.assertEqual(mensagem.remetente, self.professor)
        self.assertEqual(mensagem.conteudo, "Bom Dia, aluno!")
        self.assertEqual(mensagem.conversa, conversa)

    def test_participante_visualiza_historico_ordenado(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        msg1 = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno1,
            conteudo="Olá, professor!",
        )

        msg2 = enviar_mensagem(
            conversa=conversa,
            remetente=self.professor,
            conteudo="Olá, aluno!",
        )

        msg3 = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno1,
            conteudo="Tenho uma dúvida.",
        )

        historico = list(listar_mensagens(conversa, self.aluno1))

        self.assertEqual(len(historico), 3)
        self.assertEqual(
            [mensagem.pk for mensagem in historico],
            [msg1.pk, msg2.pk, msg3.pk],
        )

    def test_rejeita_leitura_por_usuario_nao_participante(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno1,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno1,
            conteudo="Olá, professor!",
        )

        with self.assertRaisesRegex(
            ConversaInvalidaError,
            "O usuário deve ser um dos participantes da conversa",
        ):
            list(listar_mensagens(conversa, self.aluno2))

        self.assertTrue(
            Mensagem.objects.filter(pk=mensagem.pk).exists()
        )


class HistoricoConversaViewTests(TestCase):
    def setUp(self):
        self.professor = Usuario.objects.create_user(
            username="professor",
            password="senha-teste",
            tipo=Usuario.Tipo.PROFESSOR,
        )

        self.aluno = Usuario.objects.create_user(
            username="aluno",
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

        self.disciplina.alunos.add(self.aluno)

    def test_participante_autenticado_visualiza_historico(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno,
            conteudo="Ola, professor!",
        )

        self.client.force_login(self.aluno)

        url = reverse(
            "chat:historico_conversa",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        dados = response.json()

        self.assertEqual(len(dados["mensagens"]), 1)
        self.assertEqual(dados["mensagens"][0]["id"], mensagem.pk)
        self.assertEqual(
            dados["mensagens"][0]["remetente_id"],
            self.aluno.pk,
        )
        self.assertEqual(
            dados["mensagens"][0]["conteudo"],
            "Ola, professor!",
        )

    def test_usuario_nao_participante_recebe_403(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        mensagem = enviar_mensagem(
            conversa=conversa,
            remetente=self.aluno,
            conteudo="Ola, professor!",
        )

        self.client.force_login(self.aluno2)

        url = reverse(
            "chat:historico_conversa",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Mensagem.objects.filter(pk=mensagem.pk).exists()
        )

    def test_usuario_nao_autenticado_e_redirecionado(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        url = reverse(
            "chat:historico_conversa",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.get(url)   

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"next={url}", response["Location"])

    def test_conversa_inexistente_retorna_404(self):  
        self.client.force_login(self.aluno)

        url = reverse(
            "chat:historico_conversa",
            kwargs={"conversa_id": 999},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)  

    def test_participante_envia_mensagem_via_http(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={"conteudo": "Olá, professor!"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Mensagem.objects.count(), 1)

        dados = response.json()

        self.assertEqual(dados["conteudo"], "Olá, professor!")
        self.assertEqual(dados["remetente_id"], self.aluno.pk)

    def test_ignora_remetente_id_enviado_pelo_cliente(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={
                "conteudo": "Olá!",
                "remetente_id": self.professor.pk,
            },
        )

        self.assertEqual(response.status_code, 201)

        mensagem = Mensagem.objects.get(conversa=conversa)

        self.assertEqual(mensagem.remetente, self.aluno)
        self.assertNotEqual(mensagem.remetente, self.professor)

    def test_usuario_nao_participante_nao_envia_mensagem(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )  

        self.client.force_login(self.aluno2)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={
                "conteudo": "Mensagem indevida",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Mensagem.objects.count(), 0) 

    def test_mensagem_vazia_retorna_400(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={
                "conteudo": "           ",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["erro"],
            "O conteúdo da mensagem não pode estar vazio.",
        ) 
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_envio_sem_token_csrf_retorna_403(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = cliente.post(
            url,
            data={"conteudo": "Olá, professor!"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_envio_por_get_retorna_405(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_usuario_nao_autenticado_nao_envia_mensagem(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={"conteudo": "Olá, professor!"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Mensagem.objects.count(), 0)
        self.assertIn(f"next={url}", response["Location"])                

    def test_envio_para_conversa_inexistente_retorna_404(self):
        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": 999},
        )

        response = self.client.post(
            url,
            data={"conteudo": "Olá!"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_envio_sem_campo_conteudo_retorna_400(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )
        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(url, data={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["erro"],
            "O conteúdo da mensagem não pode estar vazio.",
        )
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_envio_com_conteudo_vazio_retorna_400(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )
        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={"conteudo": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["erro"],
            "O conteúdo da mensagem não pode estar vazio.",
        )
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_professor_envia_mensagem_via_http(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )
        self.client.force_login(self.professor)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={"conteudo": "Bom dia, aluno!"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Mensagem.objects.count(), 1)

        dados = response.json()
        mensagem = Mensagem.objects.get(pk=dados["id"])

        self.assertEqual(dados["remetente_id"], self.professor.pk)
        self.assertEqual(dados["conteudo"], "Bom dia, aluno!")
        self.assertEqual(mensagem.remetente, self.professor)
        self.assertEqual(mensagem.conversa, conversa)
        self.assertEqual(mensagem.conteudo, "Bom dia, aluno!")

    def test_envio_remove_espacos_externos(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )
        self.client.force_login(self.aluno)

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.post(
            url,
            data={"conteudo": "  Olá, professor!  "},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["conteudo"],
            "Olá, professor!",
        )
        self.assertEqual(Mensagem.objects.count(), 1)

        mensagem = Mensagem.objects.get(pk=response.json()["id"])

        self.assertEqual(mensagem.conteudo, "Olá, professor!")
        self.assertEqual(mensagem.remetente, self.aluno)
        self.assertEqual(mensagem.conversa, conversa)

    def test_historico_retorna_mensagens_em_ordem(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        url_envio = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        envios = [
            (self.aluno, "Olá, professor!"),
            (self.professor, "Olá, aluno!"),
            (self.aluno, "Tenho uma dúvida."),
        ]
        ids_esperados = []

        for remetente, conteudo in envios:
            self.client.force_login(remetente)
            response = self.client.post(
                url_envio,
                data={"conteudo": conteudo},
            )

            self.assertEqual(response.status_code, 201)
            ids_esperados.append(response.json()["id"])

        self.client.force_login(self.aluno)

        url_historico = reverse(
            "chat:historico_conversa",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.get(url_historico)

        self.assertEqual(response.status_code, 200)

        historico = response.json()["mensagens"]

        self.assertEqual(len(historico), 3)
        self.assertEqual(
            [mensagem["id"] for mensagem in historico],
            ids_esperados,
        )
        self.assertEqual(
            [mensagem["conteudo"] for mensagem in historico],
            [conteudo for _, conteudo in envios],
        )
        self.assertEqual(
            list(
                Mensagem.objects.filter(conversa=conversa)
                .order_by("enviada_em", "pk")
                .values_list("pk", flat=True)
            ),
            ids_esperados,
        )

    def test_historico_conversa_vazia_retorna_lista_vazia(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )
        self.client.force_login(self.aluno)

        url = reverse(
            "chat:historico_conversa",
            kwargs={"conversa_id": conversa.pk},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"mensagens": []})
        self.assertEqual(Mensagem.objects.count(), 0)

    def test_multiplas_mensagens_sao_persistidas(self):
        conversa = criar_ou_obter_conversa(
            aluno=self.aluno,
            professor=self.professor,
            disciplina=self.disciplina,
        )

        url = reverse(
            "chat:enviar_mensagem",
            kwargs={"conversa_id": conversa.pk},
        )

        envios = [
            (self.aluno, "Bom dia!"),
            (self.professor, "Bom dia! Qual é a dúvida?"),
            (self.aluno, "Como implementar uma pilha?"),
            (self.professor, "Podemos começar usando uma lista."),
        ]
        ids_criados = []

        for remetente, conteudo in envios:
            with self.subTest(
                remetente=remetente.username,
                conteudo=conteudo,
            ):
                self.client.force_login(remetente)

                response = self.client.post(
                    url,
                    data={"conteudo": conteudo},
                )

                self.assertEqual(response.status_code, 201)

                dados = response.json()
                ids_criados.append(dados["id"])

                self.assertEqual(dados["remetente_id"], remetente.pk)
                self.assertEqual(dados["conteudo"], conteudo)

        self.assertEqual(Mensagem.objects.count(), len(envios))

        for mensagem_id, (remetente, conteudo) in zip(
            ids_criados, envios
        ):
            mensagem = Mensagem.objects.get(pk=mensagem_id)

            self.assertEqual(mensagem.conversa, conversa)
            self.assertEqual(mensagem.remetente, remetente)
            self.assertEqual(mensagem.conteudo, conteudo)
            self.assertIsNotNone(mensagem.enviada_em)