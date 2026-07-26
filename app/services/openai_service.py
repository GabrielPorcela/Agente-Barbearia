"""
Serviço: OpenAI — Assistente de Interpretação de Intenções

Responsabilidade única deste módulo: interpretar a mensagem do cliente
e classificar a intenção em uma das 4 categorias abaixo, extraindo as
entidades relevantes (data, horário, serviço etc.) em formato estruturado.

IMPORTANTE:
- A IA NÃO decide nem executa nenhuma ação (não agenda, não cancela,
  não consulta o banco). Ela apenas interpreta o texto e devolve um JSON.
- Toda a lógica de negócio (validações, agendamento, cancelamento,
  consulta de horários) permanece 100% em Python, nos services
  correspondentes (ex: agendamento_service.py).

Intenções suportadas:
- "agendar"
- "consultar_agenda"
- "cancelar"
- "conversa_normal"
"""

import json
import os

from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

INTENCOES_VALIDAS = {"agendar", "consultar_agenda", "cancelar", "conversa_normal"}

ENTIDADES_PADRAO = {
    "nome_cliente": None,
    "telefone": None,
    "servico": None,
    "data": None,       # formato esperado: AAAA-MM-DD
    "horario": None,    # formato esperado: HH:MM
    "agendamento_id": None,
}

_SYSTEM_PROMPT = """
Você é um classificador de intenções para o atendimento de uma barbearia via WhatsApp.

Sua única tarefa é interpretar a mensagem do cliente e devolver um JSON estruturado.
Você NÃO deve responder ao cliente, nem tomar nenhuma decisão de negócio.
Apenas classifique a intenção e extraia as informações presentes na mensagem.

Intenções possíveis (escolha exatamente uma):
- "agendar": o cliente quer marcar um horário/serviço.
- "consultar_agenda": o cliente quer saber horários disponíveis ou ver agendamentos existentes.
- "cancelar": o cliente quer cancelar um agendamento existente.
- "conversa_normal": qualquer outra mensagem (saudação, dúvida geral, elogio, etc.)
  que não se encaixe claramente nas três anteriores.

Responda SOMENTE com um JSON no seguinte formato, sem nenhum texto adicional,
sem markdown e sem comentários:

{
  "intencao": "agendar" | "consultar_agenda" | "cancelar" | "conversa_normal",
  "entidades": {
    "nome_cliente": string ou null,
    "telefone": string ou null,
    "servico": string ou null,
    "data": string no formato AAAA-MM-DD ou null,
    "horario": string no formato HH:MM ou null,
    "agendamento_id": inteiro ou null
  }
}

Regras:
- Se um dado não estiver presente na mensagem, use null. Nunca invente informação.
- Só preencha "data" e "horario" se conseguir identificá-los com clareza
  (datas relativas como "amanhã" ou "sexta-feira" podem ser deixadas como null
  se não for possível ter certeza).
- O campo "telefone" só deve ser preenchido se o cliente mencionar um número
  explicitamente na própria mensagem de texto.
- O campo "agendamento_id" só deve ser preenchido se o cliente citar um número
  de identificação de agendamento explicitamente.
""".strip()


# ---------------------------------------------------------------------------
# Cliente OpenAI (lazy init, para não falhar na importação sem API key)
# ---------------------------------------------------------------------------
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY não configurada. Defina essa variável no arquivo .env."
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------
def interpretar_intencao(mensagem: str) -> dict:
    """
    Interpreta a mensagem do cliente usando a API da OpenAI e retorna
    a intenção identificada junto com as entidades extraídas.

    Esta função NÃO executa nenhuma ação — apenas classifica e extrai dados.
    Quem decide o que fazer com o resultado é a camada de aplicação em Python.

    Args:
        mensagem: texto enviado pelo cliente via WhatsApp.

    Returns:
        Dicionário no formato:
        {
            "intencao": "agendar" | "consultar_agenda" | "cancelar" | "conversa_normal",
            "entidades": {
                "nome_cliente": str | None,
                "telefone": str | None,
                "servico": str | None,
                "data": str | None,
                "horario": str | None,
                "agendamento_id": int | None,
            }
        }

        Em caso de mensagem vazia ou qualquer falha ao chamar a API
        (rede, autenticação, resposta inválida etc.), retorna um fallback
        seguro com intenção "conversa_normal" e entidades vazias.
    """
    mensagem = (mensagem or "").strip()

    if not mensagem:
        return {"intencao": "conversa_normal", "entidades": dict(ENTIDADES_PADRAO)}

    try:
        client = _get_client()
        resposta = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": mensagem},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        conteudo = resposta.choices[0].message.content
        dados = json.loads(conteudo)
    except Exception as erro:
        import traceback

        print("\n========== ERRO OPENAI ==========")
        traceback.print_exc()
        print("=================================\n")

        return {
        "intencao": "conversa_normal",
        "entidades": dict(ENTIDADES_PADRAO)
        }

    return _normalizar_resultado(dados)


def _normalizar_resultado(dados: dict) -> dict:
    """
    Garante que o resultado sempre tenha o formato esperado, mesmo que a IA
    retorne campos faltando ou uma intenção fora do conjunto permitido.
    """
    intencao = dados.get("intencao")
    if intencao not in INTENCOES_VALIDAS:
        intencao = "conversa_normal"

    entidades = dict(ENTIDADES_PADRAO)
    entidades.update(dados.get("entidades") or {})

    # Mantém apenas as chaves conhecidas, ignorando qualquer campo extra
    # que a IA eventualmente inclua na resposta.
    entidades = {chave: entidades.get(chave) for chave in ENTIDADES_PADRAO}

    return {"intencao": intencao, "entidades": entidades}
