# Barbearia Bot — MVP de Atendimento via WhatsApp

Sistema de atendimento inteligente para barbearia, com agendamento,
cancelamento e consulta de agenda via WhatsApp, usando OpenAI para
interpretação de linguagem natural.

> **Status atual:** MVP funcional completo — banco de dados, agenda,
> agente de IA, painel admin e integração com a WhatsApp Cloud API
> (webhook validado com assinatura HMAC-SHA256) implementados e revisados.

## Stack

- Python
- Flask
- SQLite
- SQLAlchemy (via Flask-SQLAlchemy)
- OpenAI API
- (sem LangChain nesta versão)

## Estrutura do projeto

```
barbearia-bot/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Configurações (dev/produção)
│   ├── database.py          # Instância do SQLAlchemy
│   ├── models/
│   │   ├── __init__.py
│   │   ├── cliente.py
│   │   ├── servico.py
│   │   └── agendamento.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── whatsapp.py      # Webhook do WhatsApp
│   │   └── admin.py         # Rotas administrativas
│   └── services/
│       ├── __init__.py
│       ├── whatsapp_service.py
│       ├── openai_service.py
│       └── agendamento_service.py
├── instance/                 # Banco SQLite fica aqui (gerado ao rodar init_db.py)
├── tests/
│   └── __init__.py
├── .env.example
├── .gitignore
├── init_db.py                # Cria o banco e as tabelas
├── requirements.txt
├── run.py
└── README.md
```

## Banco de dados (implementado)

3 tabelas, via SQLAlchemy + SQLite:

**clientes**
| campo    | tipo         |
|----------|--------------|
| id       | Integer (PK) |
| nome     | String(120)  |
| telefone | String(20), único |

**servicos**
| campo    | tipo         |
|----------|--------------|
| id       | Integer (PK) |
| nome     | String(120)  |
| duracao  | Integer (minutos) |

**agendamentos**
| campo       | tipo                        |
|-------------|-----------------------------|
| id          | Integer (PK)                |
| cliente_id  | FK -> clientes.id           |
| servico_id  | FK -> servicos.id           |
| data        | Date                        |
| horario     | Time                        |
| status      | String(20), default="agendado" |

## Fluxo de atendimento conectado

```
Cliente envia mensagem (WhatsApp)
        ↓
IA interpreta                → app/services/openai_service.py       (interpretar_intencao)
        ↓
Python executa                → app/services/atendimento_service.py  (processar_mensagem)
                                 + app/services/agendamento_service.py
        ↓
Banco de dados responde       → app/models (Cliente, Servico, Agendamento)
        ↓
Cliente recebe resposta       → app/services/whatsapp_service.py     (enviar_mensagem)
```

Ponto de entrada HTTP: `POST /whatsapp/webhook` (`app/routes/whatsapp.py`), que:
1. valida a assinatura HMAC-SHA256 do payload (`whatsapp_service.validar_assinatura`),
   usando o header `X-Hub-Signature-256` e o `WHATSAPP_APP_SECRET` — requisições com
   assinatura inválida são rejeitadas com `403`;
2. extrai telefone + texto do payload recebido (`whatsapp_service.extrair_mensagem_recebida`);
3. chama `atendimento_service.processar_mensagem(telefone, mensagem)`, que por sua vez
   chama a IA **uma única vez** para classificar a intenção e, a partir daí, decide tudo
   em Python puro (validações, consulta/gravação no banco, texto de resposta);
4. envia a resposta de volta com `whatsapp_service.enviar_mensagem`.

Sem credenciais do WhatsApp configuradas no `.env`, `enviar_mensagem` apenas imprime a
resposta no console — útil para testar o fluxo localmente sem uma conta Business configurada.

Sem `WHATSAPP_APP_SECRET` configurado, a validação de assinatura é ignorada (um aviso é
registrado no log) — permite testar o webhook localmente antes de configurar o App da Meta,
mas **deve ser configurado antes de ir para produção**.

Qualquer erro inesperado durante o processamento da mensagem é capturado, registrado no
log (`logger.exception`) e a rota ainda assim responde `200` para a Meta — isso evita que
o WhatsApp reenvie o mesmo webhook em loop (o que poderia gerar agendamentos duplicados).

## Assistente de IA (interpretação de intenções)

O arquivo `app/services/openai_service.py` implementa a função:

```python
interpretar_intencao(mensagem: str) -> dict
```

Ela usa a API da OpenAI **apenas para interpretar** o texto do cliente e
devolver um JSON estruturado com a intenção e as entidades extraídas.
A IA não decide nem executa nenhuma ação — todo o resto (agendar, cancelar,
consultar) é lógica pura em Python, nos services correspondentes.

Intenções suportadas (exatamente 4):

| Intenção            | Quando é identificada                                   |
|---------------------|----------------------------------------------------------|
| `agendar`           | cliente quer marcar um horário/serviço                   |
| `consultar_agenda`  | cliente quer saber horários ou ver agendamentos          |
| `cancelar`          | cliente quer cancelar um agendamento existente           |
| `conversa_normal`   | qualquer outra mensagem (saudação, dúvida geral etc.)    |

Formato de retorno:

```python
{
    "intencao": "agendar",
    "entidades": {
        "nome_cliente": "Gabriel",
        "telefone": None,
        "servico": "Corte de cabelo",
        "data": "2026-07-10",
        "horario": "14:00",
        "agendamento_id": None
    }
}
```

Se a chamada à API falhar por qualquer motivo (sem `OPENAI_API_KEY`, erro de
rede, resposta em formato inválido etc.), a função retorna um fallback seguro:
`intencao="conversa_normal"` com todas as entidades nulas — o atendimento
nunca quebra por causa da camada de IA.

Modelo usado por padrão: `gpt-4o-mini` (configurável via `OPENAI_MODEL` no `.env`).

## Como rodar (setup inicial)

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# preencher as variáveis do .env (pelo menos SECRET_KEY e DATABASE_URL;
# para o WhatsApp funcionar de verdade, também WHATSAPP_API_TOKEN,
# WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN e WHATSAPP_APP_SECRET)

python init_db.py   # cria instance/barbearia.db com as 3 tabelas
flask run
```

## Logs

O nível de log é configurável via `LOG_LEVEL` no `.env` (padrão: `INFO`). A configuração
é centralizada em `app/__init__.py` (`_configurar_logging`); cada módulo usa
`logging.getLogger(__name__)`. Eventos registrados incluem: verificação do webhook,
assinaturas inválidas, falhas ao chamar a Graph API do WhatsApp e erros inesperados
no processamento de mensagens.

## Segurança básica

- O webhook `POST /whatsapp/webhook` valida a assinatura HMAC-SHA256 de cada requisição
  antes de processá-la (ver seção "Fluxo de atendimento conectado" acima).
- Nenhuma credencial é hardcoded no código — tudo vem do `.env` (que está no `.gitignore`).
- O agente de IA nunca executa ações diretamente no banco — apenas classifica texto,
  reduzindo a superfície de risco de uma resposta inesperada da IA.

## Observação

O arquivo `app/models/barbeiro.py` existe na estrutura do projeto, mas não está em uso:
não é importado em `app/models/__init__.py` e o model `Agendamento` não possui `barbeiro_id`
nem relacionamento com `Barbeiro`. Foi mantido como está (sem alterar o banco ou remover o
arquivo) para não impactar a estrutura de dados existente; fica como ponto de atenção caso
o suporte a múltiplos barbeiros seja implementado futuramente.

## Próximos passos (fora do escopo desta entrega)

1. Suportar múltiplos barbeiros (ativar o model `Barbeiro`, ligando-o a `Agendamento`).
2. Testes automatizados (a pasta `tests/` está reservada, mas ainda vazia).
3. Deploy em produção (gunicorn já está no `requirements.txt`).
