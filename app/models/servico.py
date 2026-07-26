"""
Modelo: Servico

Tabela: servicos
Campos: id, nome, duracao
"""

from app.database import db


class Servico(db.Model):
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    duracao = db.Column(db.Integer, nullable=False)  # duração em minutos

    agendamentos = db.relationship("Agendamento", back_populates="servico")

    def __repr__(self) -> str:
        return f"<Servico id={self.id} nome={self.nome!r} duracao={self.duracao}>"
