"""
Script de inicialização do banco de dados.

Cria o arquivo SQLite (instance/barbearia.db) e todas as tabelas
definidas nos modelos: Cliente, Servico, Agendamento.

Uso:
    python init_db.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.database import db  # noqa: E402


def init_db() -> None:
    app = create_app(env=os.getenv("FLASK_ENV", "production"))

    with app.app_context():
        db.create_all()
        print("Banco de dados inicializado com sucesso em instance/barbearia.db")
        print("Tabelas criadas:", list(db.metadata.tables.keys()))


if __name__ == "__main__":
    init_db()
