"""
Instância central do SQLAlchemy.

Mantida em módulo separado para evitar import circular entre
app/__init__.py e app/models/*.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
