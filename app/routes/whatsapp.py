"""
Blueprint: WhatsApp

Recebe as mensagens do webhook do WhatsApp e executa o fluxo completo
de atendimento:

    Cliente envia mensagem
        -> Assinatura é validada    (whatsapp_service.validar_assinatura)
        -> IA interpreta            (dentro de atendimento_service)
        -> Python executa           (atendimento_service + agendamento_service)
        -> Banco de dados responde  (SQLAlchemy)
        -> Cliente recebe resposta  (whatsapp_service.enviar_mensagem)
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from app.services import whatsapp_service
from app.services.atendimento_service import processar_mensagem

logger = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/whatsapp")


@whatsapp_bp.route("/webhook", methods=["GET"])
def verificar_webhook():
    """
    Endpoint de verificação do webhook, no padrão exigido pela
    Meta WhatsApp Cloud API (hub.mode / hub.verify_token / hub.challenge).
    """
    modo = request.args.get("hub.mode")
    token_recebido = request.args.get("hub.verify_token")
    desafio = request.args.get("hub.challenge", "")

    token_esperado = current_app.config.get("WHATSAPP_VERIFY_TOKEN")

    if modo == "subscribe" and token_recebido and token_recebido == token_esperado:
        logger.info("Webhook do WhatsApp verificado com sucesso pela Meta.")
        return desafio, 200

    logger.warning("Tentativa de verificação de webhook com token inválido.")
    return "Token de verificação inválido.", 403


@whatsapp_bp.route("/webhook", methods=["POST"])
def receber_mensagem():
    """
    Recebe a mensagem enviada pelo cliente, processa o fluxo completo
    de atendimento e envia a resposta de volta via WhatsApp.

    Sempre responde 200 (exceto em caso de assinatura inválida), mesmo
    quando ocorre um erro interno no processamento: é o comportamento
    recomendado pela Meta para evitar que o mesmo webhook seja reenviado
    repetidamente, o que poderia gerar agendamentos duplicados.
    """
    app_secret = current_app.config.get("WHATSAPP_APP_SECRET")
    assinatura_header = request.headers.get("X-Hub-Signature-256")

    if not whatsapp_service.validar_assinatura(request.get_data(), assinatura_header, app_secret):
        logger.warning("Webhook do WhatsApp recebido com assinatura inválida — requisição rejeitada.")
        return jsonify({"status": "assinatura_invalida"}), 403

    payload = request.get_json(silent=True) or {}

    dados = whatsapp_service.extrair_mensagem_recebida(payload)
    if dados is None:
        # Payload sem mensagem de texto reconhecível
        # (ex: confirmação de entrega/leitura enviada pela própria API).
        return jsonify({"status": "ignorado"}), 200

    try:
        resposta = processar_mensagem(dados["telefone"], dados["mensagem"])
        whatsapp_service.enviar_mensagem(dados["telefone"], resposta)
    except Exception:
        logger.exception("Erro ao processar mensagem do telefone %s", dados["telefone"])
        return jsonify({"status": "erro_interno"}), 200

    return jsonify({"status": "processado"}), 200
