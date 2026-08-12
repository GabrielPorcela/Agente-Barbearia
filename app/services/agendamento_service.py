"""
Serviço: Agenda

Implementa as regras de negócio da agenda da barbearia:
- consultar_horarios(): horários livres em uma data, para um serviço
- agendar(): cria um novo agendamento
- cancelar(): cancela um agendamento existente
- listar_agenda(): lista os agendamentos (com filtro opcional por data)

Sem uso de IA — apenas lógica determinística sobre o banco de dados.
"""

from datetime import date, datetime, time, timedelta

from app.database import db
from app.models import Agendamento, Cliente, Servico

# ---------------------------------------------------------------------------
# Configuração do funcionamento da barbearia
# ---------------------------------------------------------------------------
HORARIO_ABERTURA = time(9, 0)
HORARIO_FECHAMENTO = time(19, 0)
INTERVALO_SLOT_MINUTOS = 30


# ---------------------------------------------------------------------------
# Funções auxiliares (internas)
# ---------------------------------------------------------------------------
def _gerar_slots_do_dia() -> list:
    """Gera a lista de horários possíveis no dia, de acordo com o intervalo de slot."""
    slots = []
    atual = datetime.combine(date.today(), HORARIO_ABERTURA)
    fim = datetime.combine(date.today(), HORARIO_FECHAMENTO)

    while atual < fim:
        slots.append(atual.time())
        atual += timedelta(minutes=INTERVALO_SLOT_MINUTOS)

    return slots


def _intervalos_se_sobrepoe(inicio_a: time, duracao_a: int, inicio_b: time, duracao_b: int) -> bool:
    """Verifica se dois intervalos de horário (início + duração em minutos) se sobrepõem."""
    base = date.today()

    inicio_dt_a = datetime.combine(base, inicio_a)
    fim_dt_a = inicio_dt_a + timedelta(minutes=duracao_a)

    inicio_dt_b = datetime.combine(base, inicio_b)
    fim_dt_b = inicio_dt_b + timedelta(minutes=duracao_b)

    return inicio_dt_a < fim_dt_b and inicio_dt_b < fim_dt_a


def _buscar_servico_ou_falhar(servico_id: int) -> Servico:
    servico = Servico.query.get(servico_id)
    if servico is None:
        raise ValueError(f"Serviço com id {servico_id} não encontrado.")
    return servico


# ---------------------------------------------------------------------------
# Funções principais
# ---------------------------------------------------------------------------
def consultar_horarios(data_consulta: date, servico_id: int) -> list:
    """
    Retorna os horários disponíveis em uma data, considerando a duração
    do serviço informado e os agendamentos já existentes (status "agendado").

    Args:
        data_consulta: data desejada para a consulta.
        servico_id: id do serviço a ser realizado.

    Returns:
        Lista de horários (datetime.time) disponíveis, em ordem crescente.
    """
    servico = _buscar_servico_ou_falhar(servico_id)

    agendamentos_do_dia = (
        Agendamento.query
        .filter(Agendamento.data == data_consulta, Agendamento.status == "agendado")
        .all()
    )

    horarios_disponiveis = []

    for slot in _gerar_slots_do_dia():
        fim_slot = datetime.combine(date.today(), slot) + timedelta(minutes=servico.duracao)
        if fim_slot.time() > HORARIO_FECHAMENTO:
            # o serviço não terminaria dentro do horário de funcionamento
            continue

        conflita = any(
            _intervalos_se_sobrepoe(slot, servico.duracao, ag.horario, ag.servico.duracao)
            for ag in agendamentos_do_dia
        )

        if not conflita:
            horarios_disponiveis.append(slot)

    return horarios_disponiveis


def agendar(
    nome_cliente: str,
    telefone: str,
    servico_id: int,
    data_agendamento: date,
    horario_agendamento: time,
) -> Agendamento:
    """
    Cria um novo agendamento, criando o cliente automaticamente
    caso ele ainda não exista (identificado pelo telefone).

    Args:
        nome_cliente: nome do cliente.
        telefone: telefone do cliente (usado como identificador único).
        servico_id: id do serviço desejado.
        data_agendamento: data do agendamento.
        horario_agendamento: horário do agendamento.

    Returns:
        O objeto Agendamento criado.

    Raises:
        ValueError: se o serviço não existir ou o horário não estiver disponível.
    """
    servico = _buscar_servico_ou_falhar(servico_id)

    horarios_disponiveis = consultar_horarios(data_agendamento, servico_id)
    if horario_agendamento not in horarios_disponiveis:
        raise ValueError("Horário indisponível para o serviço selecionado.")

    cliente = Cliente.query.filter_by(telefone=telefone).first()
    if cliente is None:
        cliente = Cliente(nome=nome_cliente, telefone=telefone)
        db.session.add(cliente)
        db.session.flush()  # garante o id do cliente antes de criar o agendamento
    elif nome_cliente and cliente.nome != nome_cliente:
        cliente.nome = nome_cliente

    novo_agendamento = Agendamento(
        cliente_id=cliente.id,
        servico_id=servico.id,
        data=data_agendamento,
        horario=horario_agendamento,
        status="agendado",
    )
    db.session.add(novo_agendamento)
    db.session.commit()

    return novo_agendamento


def cancelar(agendamento_id: int) -> Agendamento:
    """
    Cancela um agendamento existente, alterando seu status para "cancelado".

    Args:
        agendamento_id: id do agendamento a ser cancelado.

    Returns:
        O objeto Agendamento atualizado.

    Raises:
        ValueError: se o agendamento não existir ou já estiver cancelado.
    """
    agendamento = Agendamento.query.get(agendamento_id)
    if agendamento is None:
        raise ValueError(f"Agendamento com id {agendamento_id} não encontrado.")

    if agendamento.status == "cancelado":
        raise ValueError("Este agendamento já está cancelado.")

    agendamento.status = "cancelado"
    db.session.commit()

    return agendamento


def listar_agenda(data_filtro=None) -> list:
    """
    Lista os agendamentos cadastrados, em ordem de data e horário.

    Args:
        data_filtro: se informado (date), filtra apenas os agendamentos dessa data.

    Returns:
        Lista de dicionários com os dados de cada agendamento.
    """
    query = Agendamento.query

    if data_filtro is not None:
        query = query.filter(Agendamento.data == data_filtro)

    agendamentos = query.order_by(Agendamento.data, Agendamento.horario).all()

    return [
        {
            "id": ag.id,
            "cliente": ag.cliente.nome,
            "telefone": ag.cliente.telefone,
            "servico": ag.servico.nome,
            "data": ag.data.isoformat(),
            "horario": ag.horario.strftime("%H:%M"),
            "status": ag.status,
        }
        for ag in agendamentos
    ]
