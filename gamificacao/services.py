from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import EventoXP, Progresso


def conceder_xp(*, aluno, codigo, referencia_id, quantidade):
    """Concede XP uma única vez para a combinação aluno + evento + origem.

    Retorna uma tupla (evento, criado):
    - criado=True: o evento foi registrado e o XP foi somado;
    - criado=False: esse evento já tinha sido registrado e nada foi somado.

    A função deve ser chamada pela camada de serviços, não diretamente por
    views ou signals que atualizem xp_total por conta própria.
    """

    if getattr(aluno, "pk", None) is None:
        raise ValidationError("O aluno precisa estar salvo no banco de dados.")

    if getattr(aluno, "tipo", None) != "ALUNO":
        raise ValidationError("Somente usuários do tipo ALUNO podem receber XP.")

    if codigo not in EventoXP.Codigo.values:
        raise ValidationError({"codigo": "Código de evento de XP inválido."})

    if isinstance(referencia_id, bool) or not isinstance(referencia_id, int) or referencia_id <= 0:
        raise ValidationError({"referencia_id": "A referência deve ser um ID inteiro positivo."})

    if isinstance(quantidade, bool) or not isinstance(quantidade, int) or quantidade <= 0:
        raise ValidationError({"quantidade": "A quantidade de XP deve ser um inteiro positivo."})

    with transaction.atomic():
        progresso, _ = Progresso.objects.get_or_create(aluno=aluno)

        # A restrição UniqueConstraint no banco torna esta operação idempotente,
        # inclusive quando duas requisições tentam registrar a mesma recompensa.
        evento, criado = EventoXP.objects.get_or_create(
            progresso=progresso,
            codigo=codigo,
            referencia_id=referencia_id,
            defaults={"quantidade": quantidade},
        )

        if criado:
            Progresso.objects.filter(pk=progresso.pk).update(
                xp_total=F("xp_total") + quantidade,
                atualizado_em=timezone.now(),
            )
            progresso.refresh_from_db(fields=["xp_total", "atualizado_em"])

        return evento, criado
