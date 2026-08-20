"""
Script de migración manual para pasar el sistema a multi-colmado con superadmin.
Este script:
  1. Crea la tabla nueva 'plan' (si no existe).
  2. Agrega las columnas nuevas a 'colmado': plan_id, estado, configuracion.
  3. Quita el NOT NULL de 'colmado_id' en 'usuario' (para permitir superadmin sin colmado).
  4. Marca todos los colmados existentes con estado='activo' (para no dejar nulls).

Cómo correrlo:
  - En LOCAL: python migrar_db.py
  - En RENDER: abre la Shell de tu servicio web en el dashboard de Render y corre:
      python migrar_db.py

Requiere que la variable de entorno DATABASE_URL esté configurada (ya la tienes
configurada en Render; en local, asegúrate de tenerla en tu .env o exportada).
"""

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("No se encontró la variable de entorno DATABASE_URL.")

# Render a veces da la URL con 'postgres://', SQLAlchemy necesita 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    trans = conn.begin()
    try:
        # 1. Crear tabla 'plan' si no existe
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS plan (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(50) NOT NULL,
                precio FLOAT NOT NULL,
                duracion_dias INTEGER NOT NULL DEFAULT 30,
                activo BOOLEAN DEFAULT TRUE
            );
        """))
        print("OK: tabla 'plan' lista.")

        # 2. Agregar columnas nuevas a 'colmado'
        conn.execute(text("""
            ALTER TABLE colmado
            ADD COLUMN IF NOT EXISTS plan_id INTEGER REFERENCES plan(id),
            ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'activo',
            ADD COLUMN IF NOT EXISTS configuracion JSON DEFAULT '{}';
        """))
        print("OK: columnas nuevas agregadas a 'colmado'.")

        # 3. Permitir que 'usuario.colmado_id' sea NULL (para el superadmin)
        conn.execute(text("""
            ALTER TABLE usuario
            ALTER COLUMN colmado_id DROP NOT NULL;
        """))
        print("OK: 'usuario.colmado_id' ahora acepta NULL.")

        # 4. Asegurar que ningún colmado existente quede con estado vacío
        conn.execute(text("""
            UPDATE colmado SET estado = 'activo' WHERE estado IS NULL;
        """))
        print("OK: colmados existentes marcados como 'activo'.")

        trans.commit()
        print("\nMigración completada con éxito. No se borró ningún dato.")

    except Exception as e:
        trans.rollback()
        print(f"\nError durante la migración, no se aplicó ningún cambio: {e}")
        raise