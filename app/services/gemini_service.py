import json
import logging
import os
from datetime import date

from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

logger = logging.getLogger(__name__)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

INTENCOES_VALIDAS = {
    "agendar",
    "consultar_agenda",
    "cancelar",
    "conversa_normal",
}

ENTIDADES_PADRAO = {
    "nome_cliente": None,
    "telefone": None,
    "servico": None,
    "data": None,
    "horario": None,
    "agendamento_id": None,
}

hoje = date.today().isoformat()

_SYSTEM_PROMPT = f"""
Hoje é {hoje}.

Você é um classificador de intenções para atendimento de uma barbearia.

Sua única função é interpretar a mensagem do cliente e retornar SOMENTE JSON.

Formato obrigatório:

{{
  "intencao": "agendar|consultar_agenda|cancelar|conversa_normal",
  "entidades": {{
    "nome_cliente": null,
    "telefone": null,
    "servico": null,
    "data": null,
    "horario": null,
    "agendamento_id": null
  }}
}}

Regras:

- Nunca responda ao cliente.
- Nunca explique nada.
- Nunca use markdown.
- Retorne somente JSON válido.
- Nunca invente informações.
- Use null quando não encontrar dados.
- Data deve estar no formato AAAA-MM-DD.
- Converta:
  - "hoje"
  - "amanhã"
  - "segunda-feira"
  - outras datas relativas

  para a data real usando a data atual informada acima.

- Horário deve estar no formato HH:MM.
"""

_client = None


def _get_client():
    global _client

    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError("GEMINI_API_KEY não encontrada.")

        _client = genai.Client(api_key=api_key)

    return _client


def interpretar_intencao(mensagem: str):

    mensagem = (mensagem or "").strip()

    if not mensagem:
        return {
            "intencao": "conversa_normal",
            "entidades": dict(ENTIDADES_PADRAO),
        }

    try:

        client = _get_client()

        # Nota: "temperature" foi removido do config abaixo porque a família
        # de modelos Gemini 3.x (incluindo o gemini-3.6-flash usado por
        # padrão) descontinuou os parâmetros de amostragem temperature/
        # top_p/top_k — enviá-los deixou de ter efeito e passará a retornar
        # erro HTTP 400 em gerações futuras. Para manter respostas
        # determinísticas, a instrução já deixa claro no prompt que a saída
        # deve ser sempre o mesmo JSON estruturado, sem variação livre.
        resposta = client.models.generate_content(
            model=MODEL,
            contents=mensagem,
            config={
                "system_instruction": _SYSTEM_PROMPT,
            },
        )

        texto_resposta = (resposta.text or "").strip()
        # Robustez extra: mesmo com a instrução de "nunca usar markdown",
        # o modelo eventualmente envolve o JSON em ```json ... ``` — remove
        # as cercas de código antes de tentar o parse, em vez de falhar.
        if texto_resposta.startswith("```"):
            texto_resposta = texto_resposta.strip("`")
            if texto_resposta.startswith("json"):
                texto_resposta = texto_resposta[4:]
            texto_resposta = texto_resposta.strip()

        logger.debug("Resposta bruta do Gemini: %r", texto_resposta)

        dados = json.loads(texto_resposta)

    except Exception:
        logger.exception("Falha ao interpretar intenção via Gemini")

        return {
            "intencao": "conversa_normal",
            "entidades": dict(ENTIDADES_PADRAO),
        }

    return _normalizar_resultado(dados)


def _normalizar_resultado(dados):

    intencao = dados.get("intencao")

    if intencao not in INTENCOES_VALIDAS:
        intencao = "conversa_normal"

    entidades = dict(ENTIDADES_PADRAO)
    entidades.update(dados.get("entidades") or {})

    entidades = {
        chave: entidades.get(chave)
        for chave in ENTIDADES_PADRAO
    }

    return {
        "intencao": intencao,
        "entidades": entidades,
    }