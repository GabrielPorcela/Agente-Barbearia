"""
Pacote de modelos (tabelas do banco de dados).

Cada modelo fica em seu próprio arquivo:
- cliente.py
- servico.py
- agendamento.py
- barbeiro.py

Importante: TODOS os modelos precisam ser importados aqui para que fiquem
registrados no metadata do SQLAlchemy antes de qualquer chamada a
db.create_all() (feita em app/__init__.py via `from app import models`).
Um modelo que exista como arquivo mas não seja importado aqui simplesmente
não terá sua tabela criada — silenciosamente.
"""

from app.models.cliente import Cliente
from app.models.servico import Servico
from app.models.barbeiro import Barbeiro
from app.models.agendamento import Agendamento

__all__ = ["Cliente", "Servico", "Barbeiro", "Agendamento"]
