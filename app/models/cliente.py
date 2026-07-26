"""
Modelo: Cliente

Tabela: clientes
Campos: id, nome, telefone
"""

from app.database import db


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), nullable=False, unique=True)

    agendamentos = db.relationship("Agendamento", back_populates="cliente")

    def __repr__(self) -> str:
        return f"<Cliente id={self.id} nome={self.nome!r} telefone={self.telefone!r}>"
