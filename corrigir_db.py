from pathlib import Path

p = Path("app/__init__.py")
texto = p.read_text(encoding="utf-8")

texto = texto.replace(
    'database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)`r`n    elif database_url.startswith("postgresql://"):`r`n        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)',
    '''database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)'''
)

p.write_text(texto, encoding="utf-8")
print("Trecho corrigido.")
