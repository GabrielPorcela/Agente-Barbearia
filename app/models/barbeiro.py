"""
Modelo: Barbeiro

Representa o profissional que realiza os atendimentos.
Apenas estrutura de campos — sem métodos de negócio implementados.
"""

from app.database import db


class Barbeiro(db.Model):
    __tablename__ = "barbeiros"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True)

    # Relacionamento: um barbeiro pode ter vários agendamentos.
    agendamentos = db.relationship("Agendamento", back_populates="barbeiro")

    def __repr__(self) -> str:
        return f"<Barbeiro {self.nome}>"
