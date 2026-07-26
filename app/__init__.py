"""
Application Factory do Flask.
"""

import logging

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from app.config import config_by_name
from app.database import db

def create_app(env: str = "development") -> Flask:
    """
    Cria e configura a instância da aplicação Flask.

    Args:
        env: nome do ambiente ("development" ou "production").

    Returns:
        Instância configurada de Flask.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[env])

    _configurar_logging(app)

    db.init_app(app)

    # Garante que os modelos sejam registrados no metadata do SQLAlchemy
    # antes de qualquer chamada a db.create_all().
    with app.app_context():
        from app import models  # noqa: F401

    _register_blueprints(app)

    return app


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
