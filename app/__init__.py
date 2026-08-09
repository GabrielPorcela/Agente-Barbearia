"""
Application Factory do Flask.
"""

import logging
import os
import secrets

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from app.config import config_by_name
from app.database import db

logger = logging.getLogger(__name__)


def create_app(env: str = "development") -> Flask:
    """
    Cria e configura a instância da aplicação Flask.

    Args:
        env: nome do ambiente ("development" ou "production").

    Returns:
        Instância configurada de Flask.
    """
    app = Flask(__name__, instance_relative_config=True)

    config_class = config_by_name.get(env)
    if config_class is None:
        # Evita um KeyError não tratado caso FLASK_ENV venha com um valor
        # inesperado (ex.: typo na env var do Render). Cai em produção por
        # segurança (nunca em modo debug por causa de um valor de ambiente
        # inválido).
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

        db.init_app(app)

        # Garante que os modelos sejam registrados no metadata do SQLAlchemy
        # antes de qualquer chamada a db.create_all().
        with app.app_context():
            from app import models  # noqa: F401

            db.create_all()
            app.logger.info("Banco de dados conectado e tabelas criadas/verificadas com sucesso.")

        _register_blueprints(app)
        app.logger.info("Blueprints registrados com sucesso.")

        app.logger.info("Aplicação iniciada com sucesso (env=%s).", env)
    except Exception:
        app.logger.exception("Erro fatal ao inicializar a aplicação Flask.")
        raise

    return app


def _configurar_secret_key(app: Flask) -> None:
    """
    Garante que SECRET_KEY esteja definida antes da aplicação servir requisições.

    Sem SECRET_KEY, o Flask não consegue usar sessão/flash (usado nas rotas
    admin para mensagens de sucesso/erro), e qualquer chamada a flash()
    quebra com RuntimeError -> 500. Se a variável de ambiente não estiver
    configurada, gera uma chave temporária (apenas para não derrubar a
    aplicação) e avisa no log, já que essa chave não sobrevive a reinícios
    nem é compartilhada entre múltiplos workers do gunicorn.
    """
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning(
            "SECRET_KEY não definida no ambiente — foi gerada uma chave temporária "
            "apenas para esta execução. Defina SECRET_KEY nas variáveis de ambiente "
            "do Render para produção (necessário para sessão/flash funcionarem "
            "de forma consistente entre reinícios e múltiplos workers)."
        )


def _configurar_banco_de_dados(app: Flask) -> None:
    """
    Define a URI de conexão do banco de dados.

    Usa DATABASE_URL (ambiente de produção, ex.: Render) quando definida.
    Caso contrário, cai no fallback de SQLite local, criando a pasta
    instance/ automaticamente se ela ainda não existir.
    """
    os.makedirs(app.instance_path, exist_ok=True)

    # Sem isso, uma conexão do pool que o Postgres do Render (ou o próprio
    # proxy de rede) derrubou por inatividade só é detectada quando o
    # SQLAlchemy tenta usá-la de novo — e nesse ponto o erro
    # (ex.: "SSL connection has been closed unexpectedly") sobe como uma
    # exceção não tratada -> 500 aleatório na primeira requisição após um
    # período ocioso. pool_pre_ping testa a conexão antes de reutilizá-la
    # e reconecta silenciosamente se necessário; pool_recycle descarta
    # conexões antigas antes que o servidor as feche por conta própria.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Alguns provedores (Render, Heroku) fornecem a URL com o prefixo
        # legado "postgres://", que o SQLAlchemy 1.4+ não aceita mais.
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        app.logger.info("Usando banco de dados definido em DATABASE_URL.")
    else:
        caminho_sqlite = os.path.join(app.instance_path, "barbearia.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{caminho_sqlite}"
        app.logger.info(
            "DATABASE_URL não definida; usando SQLite local em %s", caminho_sqlite
        )


def _register_blueprints(app: Flask) -> None:
    """Registra os blueprints de rotas da aplicação."""
    from app.routes.whatsapp import whatsapp_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(admin_bp)


def _configurar_logging(app: Flask) -> None:
    """
    Configura o logging da aplicação a partir de LOG_LEVEL (.env).

    Centralizado aqui para que todos os módulos (routes, services)
    usem `logging.getLogger(__name__)` e sigam o mesmo formato/nível,
    sem precisar reconfigurar logging em cada arquivo.
    """
    nivel = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)

    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app.logger.setLevel(nivel)
