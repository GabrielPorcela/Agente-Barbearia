"""
Testes automatizados do webhook do WhatsApp (verificação GET e recebimento POST).

Não faz nenhuma chamada real à Graph API da Meta e não usa credenciais
reais — WHATSAPP_VERIFY_TOKEN e WHATSAPP_APP_SECRET são definidos como
valores de teste apenas para a duração de cada teste.
"""

import hashlib
import hmac
import importlib
import json
import sys

import pytest

TOKEN_TESTE = "token-de-teste-nao-real"
APP_SECRET_TESTE = "app-secret-de-teste-nao-real"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", TOKEN_TESTE)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", APP_SECRET_TESTE)
    monkeypatch.setenv("SECRET_KEY", "chave-de-teste")

    # app.config define WHATSAPP_VERIFY_TOKEN/WHATSAPP_APP_SECRET como
    # atributos de classe, lidos de os.getenv() no momento do import — o
    # que é correto em produção (as env vars do Render já existem antes
    # do processo iniciar), mas significa que, em um único processo de
    # teste, o módulo precisa ser recarregado para enxergar as env vars
    # que o monkeypatch acabou de definir neste teste.
    for nome_modulo in list(sys.modules):
        if nome_modulo == "app" or nome_modulo.startswith("app."):
            del sys.modules[nome_modulo]

    app_module = importlib.import_module("app")
    create_app = app_module.create_app

    app = create_app("development")
    app.config["TESTING"] = True

    yield app

    db = sys.modules["app.database"].db
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _assinar(payload_bruto: bytes, secret: str = APP_SECRET_TESTE) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bruto, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# GET /whatsapp/webhook — verificação do webhook pela Meta
# ---------------------------------------------------------------------------


def test_get_webhook_token_correto_retorna_challenge(client):
    resposta = client.get(
        "/whatsapp/webhook",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": TOKEN_TESTE,
            "hub.challenge": "desafio-123",
        },
    )
    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == "desafio-123"


def test_get_webhook_token_incorreto_retorna_403(client):
    resposta = client.get(
        "/whatsapp/webhook",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": "token-errado",
            "hub.challenge": "desafio-123",
        },
    )
    assert resposta.status_code == 403


def test_get_webhook_hub_mode_incorreto_retorna_403(client):
    resposta = client.get(
        "/whatsapp/webhook",
        query_string={
            "hub.mode": "unsubscribe",
            "hub.verify_token": TOKEN_TESTE,
            "hub.challenge": "desafio-123",
        },
    )
    assert resposta.status_code == 403


def test_get_webhook_challenge_vazio_com_token_correto(client):
    resposta = client.get(
        "/whatsapp/webhook",
        query_string={
            "hub.mode": "subscribe",
            "hub.verify_token": TOKEN_TESTE,
            "hub.challenge": "",
        },
    )
    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == ""


def test_get_webhook_sem_token_retorna_403(client):
    resposta = client.get(
        "/whatsapp/webhook",
        query_string={"hub.mode": "subscribe", "hub.challenge": "desafio-123"},
    )
    assert resposta.status_code == 403


def test_get_webhook_sem_challenge_com_token_correto(client):
    resposta = client.get(
        "/whatsapp/webhook",
        query_string={"hub.mode": "subscribe", "hub.verify_token": TOKEN_TESTE},
    )
    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == ""


# ---------------------------------------------------------------------------
# POST /whatsapp/webhook — recebimento de eventos (sem credenciais reais)
# ---------------------------------------------------------------------------


def test_post_webhook_sem_assinatura_retorna_403(client):
    resposta = client.post(
        "/whatsapp/webhook",
        data=json.dumps({"entry": []}),
        content_type="application/json",
    )
    assert resposta.status_code == 403


def test_post_webhook_assinatura_invalida_retorna_403(client):
    corpo = json.dumps({"entry": []}).encode("utf-8")
    resposta = client.post(
        "/whatsapp/webhook",
        data=corpo,
        content_type="application/json",
        headers={"X-Hub-Signature-256": "sha256=assinatura-invalida"},
    )
    assert resposta.status_code == 403


def test_post_webhook_json_invalido_com_assinatura_valida_e_ignorado(client):
    corpo = b"isto nao e um json valido"
    resposta = client.post(
        "/whatsapp/webhook",
        data=corpo,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _assinar(corpo)},
    )
    # get_json(silent=True) retorna None -> payload vira {} -> nenhuma
    # mensagem extraída -> ignorado com 200 (para a Meta não reenviar).
    assert resposta.status_code == 200
    assert resposta.get_json()["status"] == "ignorado"


def test_post_webhook_evento_de_status_e_ignorado(client):
    payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"statuses": [{"status": "delivered"}]}}
                ]
            }
        ]
    }
    corpo = json.dumps(payload).encode("utf-8")
    resposta = client.post(
        "/whatsapp/webhook",
        data=corpo,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _assinar(corpo)},
    )
    assert resposta.status_code == 200
    assert resposta.get_json()["status"] == "ignorado"
