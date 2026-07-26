"""
Pacote de modelos (tabelas do banco de dados).

Cada modelo fica em seu próprio arquivo:
- cliente.py
- servico.py
- agendamento.py
"""

from app.models.cliente import Cliente
from app.models.servico import Servico
from app.models.agendamento import Agendamento

__all__ = ["Cliente", "Servico", "Agendamento"]
