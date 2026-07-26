"""
Ponto de entrada da aplicação.

Uso local:
    flask run
ou
    python run.py
"""

import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app(env=os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(debug=True)
