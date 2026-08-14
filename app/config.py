"""
Configurações da aplicação.

Este módulo apenas define a estrutura de configuração.
Nenhum valor sensível deve ser hardcoded aqui — tudo vem do .env.
"""

import os


class Config:
    """Configuração base, usada em todos os ambientes."""

    SECRET_KEY = os.getenv("SECRET_KEY")

    # SQLALCHEMY_DATABASE_URI é definida dinamicamente em create_app()
    # (app/__init__.py), pois depende de DATABASE_URL (produção/Render)
    # ou do caminho da pasta instance (fallback SQLite local).
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER")
    WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    # .strip() é defensivo: é comum colar o token no painel de variáveis de
    # ambiente do Render (ou em um .env local) com um espaço ou quebra de
    # linha acidental no fim, o que faz a comparação com o valor enviado
    # pela Meta falhar silenciosamente e a verificação do webhook retornar
    # "Token de verificação inválido" mesmo com o token "certo" configurado.
    _verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    WHATSAPP_VERIFY_TOKEN = _verify_token.strip() if _verify_token else _verify_token
    # App Secret do App da Meta (Configurações > Básico), usado para validar
    # a assinatura HMAC-SHA256 (header X-Hub-Signature-256) das requisições
    # recebidas no webhook, garantindo que vieram realmente da Meta.
    _app_secret = os.getenv("WHATSAPP_APP_SECRET")
    WHATSAPP_APP_SECRET = _app_secret.strip() if _app_secret else _app_secret

    # Nível de log da aplicação (DEBUG, INFO, WARNING, ERROR).
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    """Configuração para ambiente de desenvolvimento."""

    DEBUG = True


class ProductionConfig(Config):
    """Configuração para ambiente de produção."""

    DEBUG = False


# Mapeamento usado pela factory da aplicação para escolher o ambiente correto.
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
