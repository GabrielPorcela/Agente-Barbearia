"""
Blueprint: Admin

Painel administrativo simples (server-side, com Bootstrap) para:
- Visualizar agenda
- Cancelar horário
- Cadastrar serviços
- Visualizar clientes
"""

import logging
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.database import db
from app.models import Cliente, Servico
from app.services import agendamento_service

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
def index():
    """Redireciona a raiz do admin para a tela de agenda."""
    return redirect(url_for("admin.visualizar_agenda"))


@admin_bp.route("/agenda", methods=["GET"])
def visualizar_agenda():
    """
    Exibe a agenda de atendimentos, com filtro opcional por data
    (via query string ?data=AAAA-MM-DD).
    """
    data_str = request.args.get("data", "").strip()
    data_filtro = None

    if data_str:
        try:
            data_filtro = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Data inválida. Use o seletor de data do formulário.", "warning")
            data_str = ""

    agendamentos = agendamento_service.listar_agenda(data_filtro)

    return render_template(
        "admin/agenda.html",
        agendamentos=agendamentos,
        data_filtro=data_str,
    )


@admin_bp.route("/agenda/cancelar/<int:agendamento_id>", methods=["POST"])
def cancelar_horario(agendamento_id):
    """Cancela um agendamento e retorna para a tela de agenda."""
    try:
        agendamento_service.cancelar(agendamento_id)
        flash("Agendamento cancelado com sucesso.", "success")
    except ValueError as erro:
        logger.warning("Falha ao cancelar agendamento #%s pelo admin: %s", agendamento_id, erro)
        flash(str(erro), "danger")

    data_str = request.form.get("data_filtro", "").strip()
    if data_str:
        return redirect(url_for("admin.visualizar_agenda", data=data_str))
    return redirect(url_for("admin.visualizar_agenda"))


@admin_bp.route("/servicos", methods=["GET", "POST"])
def gerenciar_servicos():
    """Cadastra novos serviços e lista os já existentes."""
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        duracao_str = request.form.get("duracao", "").strip()

        if not nome or not duracao_str:
            flash("Preencha o nome e a duração do serviço.", "warning")
        else:
            try:
                duracao = int(duracao_str)
                if duracao <= 0:
                    raise ValueError("Duração deve ser maior que zero.")
            except ValueError:
                flash("Duração deve ser um número inteiro positivo (em minutos).", "danger")
            else:
                novo_servico = Servico(nome=nome, duracao=duracao)
                db.session.add(novo_servico)
                db.session.commit()
                flash(f"Serviço '{nome}' cadastrado com sucesso.", "success")

        return redirect(url_for("admin.gerenciar_servicos"))

    servicos = Servico.query.order_by(Servico.nome).all()
    return render_template("admin/servicos.html", servicos=servicos)


@admin_bp.route("/clientes", methods=["GET"])
def visualizar_clientes():
    """Lista todos os clientes cadastrados."""
    clientes = Cliente.query.order_by(Cliente.nome).all()
    return render_template("admin/clientes.html", clientes=clientes)
