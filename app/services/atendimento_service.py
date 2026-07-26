"""
Serviço: Atendimento (orquestrador)

Este módulo conecta as peças do sistema, seguindo o fluxo:

    Cliente envia mensagem
        -> IA interpreta            (openai_service.interpretar_intencao)
        -> Python executa           (este módulo + agendamento_service)
        -> Banco de dados responde  (SQLAlchemy / models)
        -> Cliente recebe resposta  (texto devolvido para whatsapp_service.enviar_mensagem)

A IA (openai_service) é usada em UM ÚNICO PONTO: para classificar a
intenção e extrair entidades da mensagem. A partir daí, TODA a lógica
— validações, decisões, textos de resposta, acesso ao banco — é feita
em Python puro, sem nenhuma chamada adicional à IA.
"""

from datetime import date, datetime, time

from app.models import Agendamento, Cliente, Servico
from app.services import agendamento_service
from app.services.openai_service import interpretar_intencao

# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def processar_mensagem(telefone: str, mensagem: str) -> str:
    """
    Processa uma mensagem recebida de um cliente e devolve o texto de
    resposta a ser enviado de volta via WhatsApp.

    Args:
        telefone: número de telefone do cliente (identifica o remetente).
        mensagem: texto da mensagem recebida.

    Returns:
        Texto de resposta pronto para ser enviado ao cliente.
    """
    resultado = interpretar_intencao(mensagem)
    intencao = resultado["intencao"]
    entidades = resultado["entidades"]

    if intencao == "agendar":
        return _tratar_agendar(telefone, entidades)
    if intencao == "consultar_agenda":
        return _tratar_consultar_agenda(entidades)
    if intencao == "cancelar":
        return _tratar_cancelar(telefone, entidades)

    return _tratar_conversa_normal()


# ---------------------------------------------------------------------------
# Funções auxiliares (Python puro — nenhuma chamada à IA aqui)
# ---------------------------------------------------------------------------
def _buscar_servico_por_nome(nome: str) -> Servico | None:
    if not nome:
        return None
    return Servico.query.filter(Servico.nome.ilike(f"%{nome.strip()}%")).first()


def _parse_data(data_str: str) -> date | None:
    if not data_str:
        return None
    try:
        return datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_horario(horario_str: str) -> time | None:
    if not horario_str:
        return None
    try:
        return datetime.strptime(horario_str, "%H:%M").time()
    except ValueError:
        return None


def _listar_servicos_disponiveis() -> str:
    servicos = Servico.query.order_by(Servico.nome).all()
    if not servicos:
        return "No momento não há serviços cadastrados."
    linhas = [f"- {s.nome} ({s.duracao} min)" for s in servicos]
    return "Nossos serviços:\n" + "\n".join(linhas)


# ---------------------------------------------------------------------------
# Tratamento de cada intenção
# ---------------------------------------------------------------------------
def _tratar_agendar(telefone: str, entidades: dict) -> str:
    servico = _buscar_servico_por_nome(entidades.get("servico"))
    if servico is None:
        return (
            "Não consegui identificar o serviço desejado.\n"
            + _listar_servicos_disponiveis()
            + "\n\nMe diga qual serviço, a data e o horário você gostaria."
        )

    data_agendamento = _parse_data(entidades.get("data"))
    if data_agendamento is None:
        return (
            f"Certo, {servico.nome}! Para qual data e horário você gostaria de agendar? "
            "(ex: 2026-07-10 às 14:00)"
        )

    horario_agendamento = _parse_horario(entidades.get("horario"))
    if horario_agendamento is None:
        return _sugerir_horarios(
            data_agendamento,
            servico,
            prefixo=f"Para qual horário em {data_agendamento.strftime('%d/%m/%Y')}?",
        )

    nome_cliente = entidades.get("nome_cliente") or "Cliente"

    try:
        agendamento = agendamento_service.agendar(
            nome_cliente=nome_cliente,
            telefone=telefone,
            servico_id=servico.id,
            data_agendamento=data_agendamento,
            horario_agendamento=horario_agendamento,
        )
    except ValueError:
        return _sugerir_horarios(
            data_agendamento,
            servico,
            prefixo="Esse horário não está mais disponível.",
        )

    return (
        "Agendamento confirmado! ✅\n"
        f"Serviço: {servico.nome}\n"
        f"Data: {agendamento.data.strftime('%d/%m/%Y')}\n"
        f"Horário: {agendamento.horario.strftime('%H:%M')}\n"
        f"Código do agendamento: #{agendamento.id}"
    )


def _tratar_consultar_agenda(entidades: dict) -> str:
    data_consulta = _parse_data(entidades.get("data"))
    if data_consulta is None:
        return "Para qual data você quer consultar os horários? (ex: 2026-07-10)"

    servico = _buscar_servico_por_nome(entidades.get("servico"))
    if servico is None:
        return (
            "Para qual serviço você quer consultar a disponibilidade?\n"
            + _listar_servicos_disponiveis()
        )

    return _sugerir_horarios(
        data_consulta,
        servico,
        prefixo=f"Horários livres para {servico.nome} em {data_consulta.strftime('%d/%m/%Y')}:",
        todos=True,
    )


def _tratar_cancelar(telefone: str, entidades: dict) -> str:
    agendamento_id = entidades.get("agendamento_id")

    if agendamento_id is not None:
        agendamento = Agendamento.query.get(agendamento_id)
        if agendamento is None or agendamento.cliente.telefone != telefone:
            return f"Não encontrei nenhum agendamento seu com o código #{agendamento_id}."
        try:
            agendamento_service.cancelar(agendamento_id)
        except ValueError as erro:
            return str(erro)
        return f"Agendamento #{agendamento_id} cancelado com sucesso."

    cliente = Cliente.query.filter_by(telefone=telefone).first()
    if cliente is None:
        return "Não encontrei nenhum agendamento associado a este número."

    ativos = [ag for ag in cliente.agendamentos if ag.status == "agendado"]

    if not ativos:
        return "Você não possui agendamentos ativos no momento."

    if len(ativos) == 1:
        agendamento = ativos[0]
        agendamento_service.cancelar(agendamento.id)
        return (
            f"Agendamento #{agendamento.id} ({agendamento.servico.nome} em "
            f"{agendamento.data.strftime('%d/%m/%Y')} às {agendamento.horario.strftime('%H:%M')}) "
            "foi cancelado com sucesso."
        )

    linhas = [
        f"#{ag.id} - {ag.servico.nome} em {ag.data.strftime('%d/%m/%Y')} às {ag.horario.strftime('%H:%M')}"
        for ag in ativos
    ]
    return (
        "Você tem mais de um agendamento ativo. Qual deseja cancelar? "
        "Responda com o código:\n" + "\n".join(linhas)
    )


def _tratar_conversa_normal() -> str:
    return (
        "Olá! 👋 Sou o assistente virtual da barbearia. "
        "Posso te ajudar a agendar um horário, consultar a agenda ou cancelar um agendamento. "
        "Como posso ajudar hoje?"
    )


def _sugerir_horarios(data_consulta: date, servico: Servico, prefixo: str, todos: bool = False) -> str:
    horarios = agendamento_service.consultar_horarios(data_consulta, servico.id)
    if not horarios:
        return f"{prefixo} infelizmente não há horários livres para {servico.nome} nesta data."

    limite = None if todos else 5
    lista_horarios = horarios[:limite] if limite else horarios
    lista = ", ".join(h.strftime("%H:%M") for h in lista_horarios)

    return f"{prefixo} {lista}"
