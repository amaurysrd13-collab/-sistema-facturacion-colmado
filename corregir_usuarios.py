"""
Corrige nombres de usuario que tengan espacios en blanco al inicio o al final
(por ejemplo 'kiki ' en vez de 'kiki').

Cómo correrlo (en la misma terminal donde ya tienes DATABASE_URL configurado):
  python corregir_usuarios.py
"""

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("No se encontró la variable de entorno DATABASE_URL.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    trans = conn.begin()
    try:
        resultado = conn.execute(text("""
            UPDATE usuario
            SET usuario = TRIM(usuario)
            WHERE usuario != TRIM(usuario)
        """))
        trans.commit()
        print(f"Corregidos {resultado.rowcount} usuario(s) con espacios extra.")

        filas = conn.execute(text("SELECT id, usuario FROM usuario")).fetchall()
        print("\nUsuarios actuales:")
        for fila in filas:
            print(f"  id={fila[0]}  usuario='{fila[1]}'")

    except Exception as e:
        trans.rollback()
        print(f"Error: {e}")
        raise