"""
Crea el usuario superadmin del sistema.
Te pide el usuario y la clave por consola (no quedan escritos en ningún lado del código).

Cómo correrlo (en la misma terminal donde ya tienes DATABASE_URL configurado):
  python crear_superadmin.py
"""

import os
import getpass
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("No se encontró la variable de entorno DATABASE_URL.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

nombre = input("Nombre completo del superadmin: ").strip()
usuario = input("Usuario (para iniciar sesión): ").strip()
clave = getpass.getpass("Clave (no se mostrará en pantalla): ")
clave2 = getpass.getpass("Repite la clave: ")

if clave != clave2:
    raise SystemExit("Las claves no coinciden. Corre el script de nuevo.")

if not nombre or not usuario or not clave:
    raise SystemExit("Todos los campos son obligatorios.")

clave_hash = generate_password_hash(clave)

with engine.connect() as conn:
    trans = conn.begin()
    try:
        existe = conn.execute(
            text("SELECT id FROM usuario WHERE usuario = :u"),
            {"u": usuario}
        ).fetchone()

        if existe:
            raise SystemExit(f"Ya existe un usuario con el nombre de usuario '{usuario}'. Elige otro.")

        conn.execute(text("""
            INSERT INTO usuario (colmado_id, nombre, usuario, clave_hash, rol, activo)
            VALUES (NULL, :nombre, :usuario, :clave_hash, 'superadmin', TRUE)
        """), {"nombre": nombre, "usuario": usuario, "clave_hash": clave_hash})

        trans.commit()
        print(f"\nSuperadmin '{usuario}' creado con éxito.")

    except Exception as e:
        trans.rollback()
        print(f"\nError, no se creó el usuario: {e}")
        raise