"""
Application Factory do Flask.
"""

import logging
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()

from app.config import config_by_name
from app.database import db

logger = logging.getLogger(__name__)


def create_app(env: str = "development") -> Flask:
    """
    Cria e configura a instÃ¢ncia da aplicaÃ§Ã£o Flask.

    Args:
        env: nome do ambiente ("development" ou "production").

    Returns:
        InstÃ¢ncia configurada de Flask.
    """
    app = Flask(__name__, instance_relative_config=True)

    config_class = config_by_name.get(env)
    if config_class is None:
        # Evita um KeyError nÃ£o tratado caso FLASK_ENV venha com um valor
        # inesperado (ex.: typo na env var do Render). Cai em produÃ§Ã£o por
        # seguranÃ§a (nunca em modo debug por causa de um valor de ambiente
        # invÃ¡lido).
        config_class = config_by_name["production"]

    app.config.from_object(config_class)

    _configurar_logging(app)

    if env not in config_by_name:
        app.logger.warning(
            "Ambiente '%s' desconhecido; usando ProductionConfig como fallback seguro.", env
        )

    try:
        _configurar_secret_key(app)
        _configurar_banco_de_dados(app)
        _verificar_config_whatsapp(app)

        db.init_app(app)

        # Garante que os modelos sejam registrados no metadata do SQLAlchemy
        # antes de qualquer chamada a db.create_all().
        with app.app_context():
            from app import models  # noqa: F401

            db.create_all()
            app.logger.info("Banco de dados conectado e tabelas criadas/verificadas com sucesso.")

        _register_blueprints(app)
        app.logger.info("Blueprints registrados com sucesso.")

        _registrar_health_check(app)

        app.logger.info("AplicaÃ§Ã£o iniciada com sucesso (env=%s).", env)
    except Exception:
        app.logger.exception("Erro fatal ao inicializar a aplicaÃ§Ã£o Flask.")
        raise

    return app


def _configurar_secret_key(app: Flask) -> None:
    """
    Garante que SECRET_KEY esteja definida antes da aplicaÃ§Ã£o servir requisiÃ§Ãµes.

    Sem SECRET_KEY, o Flask nÃ£o consegue usar sessÃ£o/flash (usado nas rotas
    admin para mensagens de sucesso/erro), e qualquer chamada a flash()
    quebra com RuntimeError -> 500. Se a variÃ¡vel de ambiente nÃ£o estiver
    configurada, gera uma chave temporÃ¡ria (apenas para nÃ£o derrubar a
    aplicaÃ§Ã£o) e avisa no log, jÃ¡ que essa chave nÃ£o sobrevive a reinÃ­cios
    nem Ã© compartilhada entre mÃºltiplos workers do gunicorn.
    """
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning(
            "SECRET_KEY nÃ£o definida no ambiente â€” foi gerada uma chave temporÃ¡ria "
            "apenas para esta execuÃ§Ã£o. Defina SECRET_KEY nas variÃ¡veis de ambiente "
            "do Render para produÃ§Ã£o (necessÃ¡rio para sessÃ£o/flash funcionarem "
            "de forma consistente entre reinÃ­cios e mÃºltiplos workers)."
        )


def _verificar_config_whatsapp(app: Flask) -> None:
    """
    Registra, no log de inicialização, se WHATSAPP_VERIFY_TOKEN e
    WHATSAPP_APP_SECRET foram carregados do ambiente — nunca o valor em
    si, apenas se está presente/ausente. Isso existe porque, na prática,
    o sintoma mais comum de "Meta não valida o webhook" é a variável de
    ambiente simplesmente não estar definida (ou não redefinida após um
    deploy) no Render, o que hoje só aparece como um 403 genérico sem
    nenhuma pista nos logs.
    """
    if not app.config.get("WHATSAPP_VERIFY_TOKEN"):
        app.logger.warning(
            "WHATSAPP_VERIFY_TOKEN não está definida no ambiente — a "
            "verificação GET /whatsapp/webhook vai rejeitar qualquer "
            "token enviado pela Meta até essa variável ser configurada."
        )
    if not app.config.get("WHATSAPP_APP_SECRET"):
        app.logger.warning(
            "WHATSAPP_APP_SECRET não está definida no ambiente — a "
            "validação de assinatura do POST /whatsapp/webhook está "
            "desativada (modo dev). Configure-a antes de ir para produção."
        )


def _configurar_banco_de_dados(app: Flask) -> None:
    """
    Define a URI de conexÃ£o do banco de dados.

    Usa DATABASE_URL (ambiente de produÃ§Ã£o, ex.: Render) quando definida.
    Caso contrÃ¡rio, cai no fallback de SQLite local, criando a pasta
    instance/ automaticamente se ela ainda nÃ£o existir.
    """
    os.makedirs(app.instance_path, exist_ok=True)

    # Sem isso, uma conexÃ£o do pool que o Postgres do Render (ou o prÃ³prio
    # proxy de rede) derrubou por inatividade sÃ³ Ã© detectada quando o
    # SQLAlchemy tenta usÃ¡-la de novo â€” e nesse ponto o erro
    # (ex.: "SSL connection has been closed unexpectedly") sobe como uma
    # exceÃ§Ã£o nÃ£o tratada -> 500 aleatÃ³rio na primeira requisiÃ§Ã£o apÃ³s um
    # perÃ­odo ocioso. pool_pre_ping testa a conexÃ£o antes de reutilizÃ¡-la
    # e reconecta silenciosamente se necessÃ¡rio; pool_recycle descarta
    # conexÃµes antigas antes que o servidor as feche por conta prÃ³pria.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Alguns provedores (Render, Heroku) fornecem a URL com o prefixo
        # legado "postgres://", que o SQLAlchemy 1.4+ nÃ£o aceita mais.
        # Normalizamos tanto "postgres://" quanto "postgresql://" para o
        # dialeto explÃ­cito "postgresql+psycopg://", garantindo que o
        # driver psycopg 3 (jÃ¡ presente no requirements.txt) seja usado.
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        app.logger.info("Usando banco de dados definido em DATABASE_URL.")
    else:
        caminho_sqlite = os.path.join(app.instance_path, "barbearia.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{caminho_sqlite}"
        app.logger.info(
            "DATABASE_URL nÃ£o definida; usando SQLite local em %s", caminho_sqlite
        )


def _registrar_health_check(app: Flask) -> None:
    """
    Registra a rota GET /health, usada pelo Render para verificar se o
    serviço está vivo. Não faz nenhuma chamada externa (Gemini, WhatsApp,
    banco de dados) — apenas confirma que o processo Flask está de pé.
    """

    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"}), 200


def _register_blueprints(app: Flask) -> None:
    """Registra os blueprints de rotas da aplicaÃ§Ã£o."""
    from app.routes.whatsapp import whatsapp_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(admin_bp)


def _configurar_logging(app: Flask) -> None:
    """
    Configura o logging da aplicaÃ§Ã£o a partir de LOG_LEVEL (.env).

    Centralizado aqui para que todos os mÃ³dulos (routes, services)
    usem `logging.getLogger(__name__)` e sigam o mesmo formato/nÃ­vel,
    sem precisar reconfigurar logging em cada arquivo.
    """
    nivel = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)

    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app.logger.setLevel(nivel)

