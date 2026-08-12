"""
Modelo: Agendamento

Tabela: agendamentos
Campos: id, cliente (FK), servico (FK), data, horario, status
"""

from app.database import db


class Agendamento(db.Model):
    __tablename__ = "agendamentos"

    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey("servicos.id"), nullable=False)
    # Opcional: nem todo agendamento precisa ter um barbeiro específico
    # atribuído no momento da criação (ex: fluxo automático via WhatsApp).
    barbeiro_id = db.Column(db.Integer, db.ForeignKey("barbeiros.id"), nullable=True)

    data = db.Column(db.Date, nullable=False)
    horario = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="agendado")
    # Valores esperados para status: "agendado", "cancelado", "concluido"

    cliente = db.relationship("Cliente", back_populates="agendamentos")
    servico = db.relationship("Servico", back_populates="agendamentos")
    # Completa o relacionamento declarado em Barbeiro.agendamentos
    # (back_populates="barbeiro"); sem este lado, o SQLAlchemy falha ao
    # configurar o mapper assim que o modelo Barbeiro é importado.
    barbeiro = db.relationship("Barbeiro", back_populates="agendamentos")

    def __repr__(self) -> str:
        return f"<Agendamento id={self.id} data={self.data} horario={self.horario} status={self.status!r}>"
