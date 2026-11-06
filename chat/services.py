from .models import Conversa, Mensagem


class ConversaInvalidaError(Exception):
    """Exceção para violações das regras de negócio de conversas."""

class MensagemInvalidaError(Exception):
    """Exceção para violações das regras de envio de mensagens."""

class RemetenteNaoAutorizadoError(MensagemInvalidaError):
    """O remetente não participa da conversa."""

class ConteudoMensagemInvalidoError(MensagemInvalidaError):
    """O conteúdo da mensagem é inválido."""


def criar_ou_obter_conversa(aluno, professor, disciplina):
    if aluno.tipo != aluno.Tipo.ALUNO:
        raise ConversaInvalidaError(
            "O usuario informado como aluno deve possuir o tipo ALUNO."
        )

    if professor.tipo != professor.Tipo.PROFESSOR:
        raise ConversaInvalidaError(
            "O usuario informado como professor deve possuir o tipo PROFESSOR."
        )

    if disciplina.professor_id != professor.pk:
        raise ConversaInvalidaError(
            "O professor informado não é responsável pela disciplina."
        )

    if  not disciplina.alunos.filter(pk=aluno.pk).exists():
        raise ConversaInvalidaError(
            "O aluno informado não esta matriculado na disciplina."
        )

    conversa, criada = Conversa.objects.get_or_create(
        aluno=aluno,
        professor=professor,
        disciplina=disciplina,
    )

    return conversa

def enviar_mensagem(conversa, remetente, conteudo):
    if remetente.pk not in (conversa.aluno_id, conversa.professor_id):
        raise RemetenteNaoAutorizadoError(
            "O remetente deve ser um dos participantes da conversa."
        )

    conteudo = conteudo.strip()

    if not conteudo:
        raise ConteudoMensagemInvalidoError(
            "O conteúdo da mensagem não pode estar vazio."
        )

    mensagem = Mensagem.objects.create(
        conversa=conversa,
        remetente=remetente,
        conteudo=conteudo,
    )

    return mensagem

def listar_mensagens(conversa, usuario):
    if usuario.pk not in (conversa.aluno_id, conversa.professor_id):
        raise ConversaInvalidaError(
            "O usuário deve ser um dos participantes da conversa  "
            "para visualizar o histórico."
        )

    return conversa.mensagens.order_by("enviada_em", "pk")
        