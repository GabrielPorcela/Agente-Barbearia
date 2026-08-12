"""
Serviço: WhatsApp

Responsável apenas por ENVIAR e EXTRAIR mensagens do WhatsApp
(Meta WhatsApp Cloud API por padrão), além de validar a autenticidade
das requisições recebidas no webhook. Este módulo não decide o que
responder — quem decide é o atendimento_service.py.
"""

import hashlib
import hmac
import logging
import os

import requests

logger = logging.getLogger(__name__)

# Versão da Graph API da Meta, configurável via variável de ambiente para
# não deixar uma versão antiga hardcoded — atualize WHATSAPP_GRAPH_API_VERSION
# quando a Meta descontinuar a versão em uso.
WHATSAPP_GRAPH_API_VERSION = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v23.0")
GRAPH_API_URL = f"https://graph.facebook.com/{WHATSAPP_GRAPH_API_VERSION}"


def enviar_mensagem(telefone: str, texto: str) -> None:
    """
    Envia uma mensagem de texto para o telefone informado.

    Se as credenciais da WhatsApp Cloud API não estiverem configuradas
    no .env (WHATSAPP_API_TOKEN / WHATSAPP_PHONE_NUMBER_ID), a mensagem
    é apenas exibida no console — útil para rodar o projeto localmente
    sem uma conta de WhatsApp Business configurada.

    Args:
        telefone: número de telefone do destinatário (formato E.164, sem "+").
        texto: conteúdo da mensagem a ser enviada.

    Raises:
        requests.exceptions.RequestException: se a chamada à Graph API
            falhar (erro de rede, timeout ou resposta de erro HTTP).
            O erro é registrado no log antes de ser propagado, para que
            a camada que chamou esta função decida como lidar com a falha.
    """
    token = os.getenv("WHATSAPP_API_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not token or not phone_number_id:
        print(f"[WhatsApp - modo simulação] Para {telefone}:\n{texto}\n")
        return

    url = f"{GRAPH_API_URL}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto},
    }

    try:
        resposta = requests.post(url, headers=headers, json=payload, timeout=10)
        resposta.raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Falha ao enviar mensagem via WhatsApp Cloud API para %s", telefone)
        raise


def validar_assinatura(payload_bruto: bytes, assinatura_header: str | None, app_secret: str | None) -> bool:
    """
    Valida a assinatura HMAC-SHA256 enviada pela Meta no header
    'X-Hub-Signature-256', confirmando que a requisição do webhook
    realmente veio da Meta e que o corpo não foi adulterado em trânsito.

    Args:
        payload_bruto: corpo da requisição em bytes, exatamente como recebido
            (request.get_data()), sem qualquer parsing prévio.
        assinatura_header: valor do header 'X-Hub-Signature-256'
            (formato esperado: "sha256=<hash>").
        app_secret: App Secret do App configurado na Meta
            (config WHATSAPP_APP_SECRET).

    Returns:
        True se a assinatura for válida ou se app_secret não estiver
        configurado (modo de desenvolvimento local, sem validação —
        um aviso é registrado no log nesse caso). False caso a
        assinatura esteja ausente ou não confira.
    """
    if not app_secret:
        logger.warning(
            "WHATSAPP_APP_SECRET não configurado — validação de assinatura do "
            "webhook está desativada. Configure-o antes de ir para produção."
        )
        return True

    if not assinatura_header or not assinatura_header.startswith("sha256="):
        return False

    assinatura_recebida = assinatura_header.split("=", 1)[1]
    assinatura_calculada = hmac.new(
        app_secret.encode("utf-8"), payload_bruto, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(assinatura_recebida, assinatura_calculada)


def extrair_mensagem_recebida(payload: dict) -> dict | None:
    """
    Extrai telefone e texto de um payload recebido no webhook da
    Meta WhatsApp Cloud API.

    Formato esperado (resumido):
        {
          "entry": [{
            "changes": [{
              "value": {
                "messages": [{
                  "from": "5511999999999",
                  "text": {"body": "Quero agendar um corte"}
                }]
              }
            }]
          }]
        }

    Args:
        payload: corpo JSON recebido no webhook.

    Returns:
        {"telefone": str, "mensagem": str} ou None se o payload não
        contiver uma mensagem de texto reconhecível (ex: notificações
        de status de entrega, que também chegam nesse mesmo webhook).
    """
    try:
        valor = payload["entry"][0]["changes"][0]["value"]
        mensagens = valor.get("messages")
        if not mensagens:
            return None

        mensagem_bruta = mensagens[0]
        telefone = mensagem_bruta.get("from")
        texto = mensagem_bruta.get("text", {}).get("body")

        if not telefone or not texto:
            return None

        return {"telefone": telefone, "mensagem": texto}
    except (KeyError, IndexError, TypeError):
        logger.debug("Payload de webhook sem mensagem de texto reconhecível: %s", payload)
        return None
