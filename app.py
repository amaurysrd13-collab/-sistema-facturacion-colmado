from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from flask import Flask, flash, get_flashed_messages, redirect, request, session, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import func
from models import Colmado, DetalleVenta, Fiado, PagoMembresia, Plan, Producto, Usuario, Venta, db
from werkzeug.security import check_password_hash, generate_password_hash

# Carga las variables del archivo .env (ahí está tu DATABASE_URL)
load_dotenv()

app = Flask(__name__)

# Vercel/Neon a veces da la URL como "postgres://", pero SQLAlchemy necesita "postgresql://"
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
  database_url = database_url.replace("postgres://", "postgresql://", 1)

# Si no hay DATABASE_URL configurada localmente, usa SQLite por defecto para pruebas
if not database_url:
  database_url = "sqlite:///colmado.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esto-despues")

db.init_app(app)

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
  return Usuario.query.get(int(user_id))


def solo_dueno(vista):
  """Decorador: solo el rol 'dueno' puede acceder a esta ruta."""
  from functools import wraps

  @wraps(vista)
  def envoltura(*args, **kwargs):
    if current_user.rol != "dueno":
      flash("Solo el dueño puede acceder a esa sección.", "danger")
      return redirect(url_for("dashboard"))
    return vista(*args, **kwargs)

  return envoltura


def superadmin_requerido(vista):
  """Decorador: solo el rol 'superadmin' puede acceder a esta ruta."""
  from functools import wraps

  @wraps(vista)
  def envoltura(*args, **kwargs):
    if not current_user.is_authenticated or current_user.rol != "superadmin":
      return redirect(url_for("login"))
    return vista(*args, **kwargs)

  return envoltura


def estado_pill(estado):
  colores = {"activo": "pill-ok", "suspendido": "pill-pend", "eliminado": "pill-pend"}
  return f'<span class="pill {colores.get(estado, "pill-pend")}">{estado.capitalize()}</span>'


# --- DISEÑO / PLANTILLA VISUAL ---

ESTILOS = """
<style>
  :root {
    --verde: #1c7c3f;
    --verde-oscuro: #145c2d;
    --verde-claro: #e8f5ec;
    --rojo: #c0392b;
    --gris: #6b7280;
    --fondo: #f4f6f5;
    --borde: #e2e5e4;
    --texto: #1f2a24;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--fondo);
    color: var(--texto);
  }
  .topbar {
    background: var(--verde);
    color: #fff;
    padding: 14px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .topbar .brand { font-weight: 700; font-size: 1.1rem; text-decoration: none; color: #fff; }
  .topbar .salir { color: #fff; text-decoration: none; font-size: 0.9rem; opacity: 0.9; }
  .topbar .salir:hover { opacity: 1; text-decoration: underline; }
  .wrap { max-width: 900px; margin: 24px auto; padding: 0 16px; }
  .card {
    background: #fff;
    border: 1px solid var(--borde);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  h1, h2, h3 { margin-top: 0; }
  h2 { color: var(--verde-oscuro); }
  .menu { list-style: none; padding: 0; margin: 16px 0 0; display: grid; gap: 10px; }
  .menu li a {
    display: block;
    background: var(--verde-claro);
    color: var(--verde-oscuro);
    text-decoration: none;
    padding: 14px 16px;
    border-radius: 10px;
    font-weight: 600;
    transition: background 0.15s;
  }
  .menu li a:hover { background: #d5ecdc; }
  form { display: flex; flex-direction: column; gap: 12px; max-width: 420px; }
  input[type=text], input[type=password], input[type=number], input[type=date], select {
    padding: 10px 12px;
    border: 1px solid var(--borde);
    border-radius: 8px;
    font-size: 1rem;
    width: 100%;
  }
  input:focus, select:focus { outline: 2px solid var(--verde); border-color: var(--verde); }
  label { font-size: 0.95rem; display: flex; align-items: center; gap: 8px; }
  button, .btn {
    background: var(--verde);
    color: #fff;
    border: none;
    padding: 11px 18px;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    text-align: center;
  }
  button:hover, .btn:hover { background: var(--verde-oscuro); }
  .btn-link { background: none; color: var(--verde-oscuro); padding: 8px 0; font-weight: 600; }
  .btn-link:hover { text-decoration: underline; background: none; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--borde); font-size: 0.95rem; }
  th { color: var(--gris); font-weight: 600; text-transform: uppercase; font-size: 0.78rem; }
  tr:last-child td { border-bottom: none; }
  .flash { padding: 12px 16px; border-radius: 8px; margin-bottom: 14px; font-size: 0.95rem; }
  .flash-success { background: #e8f5ec; color: var(--verde-oscuro); }
  .flash-danger { background: #fdecea; color: var(--rojo); }
  .volver { margin-top: 16px; display: inline-block; }
  .pill { padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; }
  .pill-ok { background: #e8f5ec; color: var(--verde-oscuro); }
  .pill-pend { background: #fdecea; color: var(--rojo); }
  ul.simple { padding-left: 18px; }
  ul.simple li { margin-bottom: 6px; }
</style>
"""


def render_page(titulo, cuerpo_html, mostrar_nav=True):
  """Envuelve el contenido de cada ruta con el layout visual común."""
  mensajes = get_flashed_messages(with_categories=True)
  flashes_html = "".join(
      f'<div class="flash flash-{categoria}">{texto}</div>'
      for categoria, texto in mensajes
  )

  nav_html = ""
  if mostrar_nav and current_user.is_authenticated:
    inicio = "superadmin_panel" if current_user.rol == "superadmin" else "dashboard"
    nav_html = f"""
        <div class="topbar">
            <a class="brand" href="{url_for(inicio)}">🏪 ColmaWeb</a>
            <a class="salir" href="{url_for('logout')}">Salir</a>
        </div>
        """

  return f"""<!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{titulo} · ColmaWeb</title>
        {ESTILOS}
    </head>
    <body>
        {nav_html}
        <div class="wrap">
            <div class="card">
                {flashes_html}
                {cuerpo_html}
            </div>
        </div>
    </body>
    </html>"""


# --- RUTAS DE LA APLICACIÓN ---


@app.route("/")
def index():
  if not Colmado.query.first():
    return redirect(url_for("registro_inicial"))
  return redirect(url_for("login"))


@app.route("/registro-inicial", methods=["GET", "POST"])
def registro_inicial():
  if Colmado.query.first():
    return redirect(url_for("login"))

  if request.method == "POST":
    nombre_colmado = request.form.get("nombre_colmado")
    nombre_dueno = request.form.get("nombre_dueno")
    usuario = request.form.get("usuario")
    clave = request.form.get("clave")

    if not nombre_colmado or not nombre_dueno or not usuario or not clave:
      flash("Todos los campos son obligatorios.", "danger")
      return redirect(url_for("registro_inicial"))

    nuevo_colmado = Colmado(
        nombre=nombre_colmado,
        membresia_vence=datetime.utcnow() + timedelta(days=30),
        estado="activo",
    )
    db.session.add(nuevo_colmado)
    db.session.commit()

    nuevo_dueno = Usuario(
        colmado_id=nuevo_colmado.id,
        nombre=nombre_dueno,
        usuario=usuario,
        clave_hash=generate_password_hash(clave),
        rol="dueno",
    )
    db.session.add(nuevo_dueno)
    db.session.commit()

    flash(
        "¡Sistema inicializado correctamente! Ahora puedes iniciar sesión.",
        "success",
    )
    return redirect(url_for("login"))

  return render_page(
      "Registro Inicial",
      """
        <h2>Registro Inicial · ColmaWeb</h2>
        <form method="POST">
            <input type="text" name="nombre_colmado" placeholder="Nombre del Colmado" required>
            <input type="text" name="nombre_dueno" placeholder="Nombre del Dueño" required>
            <input type="text" name="usuario" placeholder="Usuario" required>
            <input type="password" name="clave" placeholder="Contraseña" required>
            <button type="submit">Registrar</button>
        </form>
        """,
      mostrar_nav=False,
  )


@app.route("/login", methods=["GET", "POST"])
def login():
  if not Colmado.query.first():
    return redirect(url_for("registro_inicial"))

  if request.method == "POST":
    user = Usuario.query.filter_by(usuario=request.form.get("usuario")).first()
    if user and not user.activo:
      flash("Este usuario está desactivado. Contacta al dueño.", "danger")
      return redirect(url_for("login"))
    if user and check_password_hash(user.clave_hash, request.form.get("clave")):
      login_user(user)

      if user.rol == "superadmin":
        return redirect(url_for("superadmin_panel"))

      colmado = Colmado.query.get(user.colmado_id)
      if colmado and colmado.estado != "activo":
        logout_user()
        flash("Este colmado está suspendido. Contacta al administrador del sistema.", "danger")
        return redirect(url_for("login"))
      if colmado and colmado.membresia_vence and colmado.membresia_vence < datetime.utcnow():
        return redirect(url_for("membresia_vencida"))
      return redirect(url_for("dashboard"))
    flash("Usuario o clave incorrectos", "danger")

  return render_page(
      "Login",
      """
        <h2>Iniciar Sesión</h2>
        <form method="POST">
            <input type="text" name="usuario" placeholder="Usuario" required>
            <input type="password" name="clave" placeholder="Contraseña" required>
            <button type="submit">Entrar</button>
        </form>
        """,
      mostrar_nav=False,
  )


@app.before_request
def verificar_membresia():
  """Bloquea el acceso a todo excepto login/logout/membresía si venció el plan."""
  if not current_user.is_authenticated:
    return
  if current_user.rol == "superadmin":
    return
  if request.endpoint in ("membresia_vencida", "logout", "static") or (
      request.endpoint and request.endpoint.startswith("superadmin")
  ):
    return
  colmado = Colmado.query.get(current_user.colmado_id)
  if colmado and colmado.membresia_vence and colmado.membresia_vence < datetime.utcnow():
    return redirect(url_for("membresia_vencida"))


@app.route("/membresia-vencida")
@login_required
def membresia_vencida():
  colmado = Colmado.query.get(current_user.colmado_id)
  cuerpo = f"""
        <h2>⚠️ Membresía Vencida</h2>
        <p>La membresía de <strong>{colmado.nombre}</strong> venció el {colmado.membresia_vence.strftime('%d/%m/%Y')}.</p>
        <p>Contacta al administrador del sistema para renovar tu plan y seguir usando ColmaWeb.</p>
        <br><a class="btn-link volver" href="{url_for('logout')}">Cerrar sesión</a>
    """
  return render_page("Membresía Vencida", cuerpo)


@app.route("/dashboard")
@login_required
def dashboard():
  if current_user.rol == "superadmin":
    return redirect(url_for("superadmin_panel"))

  opciones_comunes = f"""
            <li><a href="{url_for('productos')}">📦 Ver Productos</a></li>
            <li><a href="{url_for('nueva_venta')}">🧾 Nueva Venta</a></li>
            <li><a href="{url_for('ventas')}">📜 Historial de Ventas</a></li>
            <li><a href="{url_for('fiados')}">💳 Fiados / Deudas</a></li>
    """

  opciones_dueno = f"""
            <li><a href="{url_for('nuevo_producto')}">➕ Agregar Producto</a></li>
            <li><a href="{url_for('reportes')}">📊 Reportes</a></li>
            <li><a href="{url_for('empleados')}">👥 Empleados</a></li>
    """ if current_user.rol == "dueno" else ""

  aviso_membresia = ""
  if current_user.rol == "dueno":
    colmado = Colmado.query.get(current_user.colmado_id)
    if colmado.membresia_vence:
      dias_restantes = (colmado.membresia_vence - datetime.utcnow()).days
      if dias_restantes < 0:
        aviso_membresia = f'<div class="flash flash-danger">⚠️ Tu membresía venció el {colmado.membresia_vence.strftime("%d/%m/%Y")}.</div>'
      elif dias_restantes <= 5:
        aviso_membresia = f'<div class="flash flash-danger">⏳ Tu membresía vence en {dias_restantes} día(s) ({colmado.membresia_vence.strftime("%d/%m/%Y")}). Contacta al administrador para renovar.</div>'
      else:
        aviso_membresia = f'<p style="color:var(--gris); font-size:0.85rem;">Membresía activa hasta el {colmado.membresia_vence.strftime("%d/%m/%Y")} ({dias_restantes} días restantes)</p>'

  UMBRAL_BAJO_STOCK = 10
  productos_bajo_stock = (
      Producto.query.filter(
          Producto.colmado_id == current_user.colmado_id,
          Producto.cantidad < UMBRAL_BAJO_STOCK,
      )
      .order_by(Producto.cantidad.asc())
      .all()
  )

  aviso_stock = ""
  if productos_bajo_stock:
    nombres_bajo_stock = ", ".join(
        f"{p.nombre} ({p.cantidad})" for p in productos_bajo_stock[:5]
    )
    extra = f" y {len(productos_bajo_stock) - 5} más" if len(productos_bajo_stock) > 5 else ""
    aviso_stock = f"""
        <div class="flash flash-danger">
            📉 Poca existencia: {nombres_bajo_stock}{extra}.
            <a class="btn-link" href="{url_for('productos')}" style="margin-left:6px;">Ver productos →</a>
        </div>
    """

  cuerpo = f"""
        <h1>Hola, {current_user.nombre} 👋</h1>
        <p>Rol: <strong>{current_user.rol}</strong></p>
        {aviso_membresia}
        {aviso_stock}
        <ul class="menu">
            {opciones_comunes}
            {opciones_dueno}
        </ul>
    """
  return render_page("Dashboard", cuerpo)


@app.route("/logout")
def logout():
  logout_user()
  return redirect(url_for("login"))


# --- PRODUCTOS / INVENTARIO ---


@app.route("/productos")
@login_required
def productos():
  lista = Producto.query.filter_by(colmado_id=current_user.colmado_id).all()
  es_dueno = current_user.rol == "dueno"
  def fila_producto(p):
    acciones = ""
    if es_dueno:
      url_editar = url_for("editar_producto", producto_id=p.id)
      url_eliminar = url_for("eliminar_producto", producto_id=p.id)
      confirmacion = f"¿Eliminar {p.nombre}?"
      acciones = (
          f'<a class="btn-link" href="{url_editar}">Editar</a> · '
          f'<a class="btn-link" href="{url_eliminar}" '
          f'onclick="return confirm(\'{confirmacion}\')">Eliminar</a>'
      )
    return f"""<tr>
                <td>{p.nombre}</td><td>RD$ {p.precio:.2f}</td><td>{p.cantidad}</td>
                <td>{acciones}</td>
            </tr>"""

  filas = "".join(fila_producto(p) for p in lista) or "<tr><td colspan='4'>Aún no tienes productos registrados.</td></tr>"

  cuerpo = f"""
        <h2>📦 Productos</h2>
        <table>
            <tr><th>Nombre</th><th>Precio</th><th>Existencia</th><th></th></tr>
            {filas}
        </table>
        <br><a class="btn" href="{url_for('nuevo_producto')}">+ Agregar Producto</a>
        <br><a class="btn-link volver" href="{url_for('dashboard')}">← Volver</a>
    """
  return render_page("Productos", cuerpo)


@app.route("/productos/nuevo", methods=["GET", "POST"])
@login_required
@solo_dueno
def nuevo_producto():
  if request.method == "POST":
    nombre = request.form.get("nombre")
    precio = request.form.get("precio")
    cantidad = request.form.get("cantidad")

    if not nombre or not precio or not cantidad:
      flash("Todos los campos son obligatorios.", "danger")
      return redirect(url_for("nuevo_producto"))

    nuevo = Producto(
        colmado_id=current_user.colmado_id,
        nombre=nombre,
        precio=float(precio),
        cantidad=int(cantidad),
    )
    db.session.add(nuevo)
    db.session.commit()
    flash("Producto agregado correctamente.", "success")
    return redirect(url_for("productos"))

  cuerpo = f"""
        <h2>➕ Nuevo Producto</h2>
        <form method="POST">
            <input type="text" name="nombre" placeholder="Nombre del producto" required>
            <input type="number" step="0.01" name="precio" placeholder="Precio" required>
            <input type="number" name="cantidad" placeholder="Existencia" required>
            <button type="submit">Guardar</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('productos')}">← Volver</a>
    """
  return render_page("Nuevo Producto", cuerpo)


@app.route("/productos/<int:producto_id>/editar", methods=["GET", "POST"])
@login_required
@solo_dueno
def editar_producto(producto_id):
  producto = Producto.query.filter_by(
      id=producto_id, colmado_id=current_user.colmado_id
  ).first_or_404()

  if request.method == "POST":
    nombre = request.form.get("nombre")
    precio = request.form.get("precio")
    cantidad = request.form.get("cantidad")

    if not nombre or not precio or not cantidad:
      flash("Todos los campos son obligatorios.", "danger")
      return redirect(url_for("editar_producto", producto_id=producto.id))

    producto.nombre = nombre
    producto.precio = float(precio)
    producto.cantidad = int(cantidad)
    db.session.commit()
    flash("Producto actualizado correctamente.", "success")
    return redirect(url_for("productos"))

  cuerpo = f"""
        <h2>✏️ Editar Producto</h2>
        <form method="POST">
            <input type="text" name="nombre" placeholder="Nombre del producto" value="{producto.nombre}" required>
            <input type="number" step="0.01" name="precio" placeholder="Precio" value="{producto.precio}" required>
            <input type="number" name="cantidad" placeholder="Existencia" value="{producto.cantidad}" required>
            <button type="submit">Guardar Cambios</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('productos')}">← Volver</a>
    """
  return render_page("Editar Producto", cuerpo)


@app.route("/productos/<int:producto_id>/eliminar")
@login_required
@solo_dueno
def eliminar_producto(producto_id):
  producto = Producto.query.filter_by(
      id=producto_id, colmado_id=current_user.colmado_id
  ).first_or_404()

  tiene_ventas = DetalleVenta.query.filter_by(producto_id=producto.id).first()
  if tiene_ventas:
    flash(
        f"No se puede eliminar '{producto.nombre}' porque ya tiene ventas registradas. "
        "Puedes ponerle existencia en 0 en su lugar.",
        "danger",
    )
    return redirect(url_for("productos"))

  db.session.delete(producto)
  db.session.commit()
  flash(f"Producto '{producto.nombre}' eliminado.", "success")
  return redirect(url_for("productos"))


# --- VENTAS / FACTURACIÓN ---


@app.route("/ventas/nueva", methods=["GET", "POST"])
@login_required
def nueva_venta():
  lista = Producto.query.filter_by(colmado_id=current_user.colmado_id).all()

  if request.method == "POST":
    es_fiado = request.form.get("es_fiado") == "on"
    nombre_cliente = request.form.get("nombre_cliente", "").strip()
    telefono_cliente = request.form.get("telefono_cliente", "").strip()

    if es_fiado and not nombre_cliente:
      flash("Para una venta fiada necesitas el nombre del cliente.", "danger")
      return redirect(url_for("nueva_venta"))

    items = []
    total = 0.0
    for producto in lista:
      cantidad_str = request.form.get(f"cantidad_{producto.id}", "0")
      try:
        cantidad = int(cantidad_str) if cantidad_str else 0
      except ValueError:
        cantidad = 0

      if cantidad <= 0:
        continue

      if cantidad > producto.cantidad:
        flash(f"No hay suficiente existencia de '{producto.nombre}'.", "danger")
        return redirect(url_for("nueva_venta"))

      items.append((producto, cantidad))
      total += producto.precio * cantidad

    if not items:
      flash("Debes seleccionar al menos un producto con cantidad.", "danger")
      return redirect(url_for("nueva_venta"))

    venta = Venta(
        colmado_id=current_user.colmado_id,
        usuario_id=current_user.id,
        total=total,
        es_fiado=es_fiado,
    )
    db.session.add(venta)
    db.session.flush()

    for producto, cantidad in items:
      detalle = DetalleVenta(
          venta_id=venta.id,
          producto_id=producto.id,
          cantidad=cantidad,
          precio_unitario=producto.precio,
      )
      db.session.add(detalle)
      producto.cantidad -= cantidad
      producto.unidades_vendidas = (producto.unidades_vendidas or 0) + cantidad

    if es_fiado:
      fiado = Fiado(
          colmado_id=current_user.colmado_id,
          venta_id=venta.id,
          nombre_cliente=nombre_cliente,
          telefono_cliente=telefono_cliente,
          monto_total=total,
          monto_pagado=0.0,
          saldado=False,
      )
      db.session.add(fiado)

    db.session.commit()
    flash(f"Venta registrada. Total: RD$ {total:.2f}", "success")
    return redirect(url_for("recibo", venta_id=venta.id))

  filas = "".join(
      f"""<tr>
                <td>{p.nombre}</td>
                <td>RD$ {p.precio:.2f}</td>
                <td>{p.cantidad} disp.</td>
                <td><input type="number" name="cantidad_{p.id}" min="0" max="{p.cantidad}" value="0" style="width:80px"></td>
            </tr>"""
      for p in lista
  ) or "<tr><td colspan='4'>No tienes productos registrados aún.</td></tr>"

  cuerpo = f"""
        <h2>🧾 Nueva Venta</h2>
        <form method="POST">
            <table>
                <tr><th>Producto</th><th>Precio</th><th>Existencia</th><th>Cant. a vender</th></tr>
                {filas}
            </table>
            <label><input type="checkbox" name="es_fiado"> Es venta fiada (a crédito)</label>
            <input type="text" name="nombre_cliente" placeholder="Nombre del cliente (si es fiado)">
            <input type="text" name="telefono_cliente" placeholder="Teléfono del cliente (opcional)">
            <button type="submit">Registrar Venta</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('dashboard')}">← Volver</a>
    """
  return render_page("Nueva Venta", cuerpo)


@app.route("/ventas")
@login_required
def ventas():
  lista = (
      Venta.query.filter_by(colmado_id=current_user.colmado_id)
      .order_by(Venta.fecha.desc())
      .all()
  )
  filas = "".join(
      f"""<tr>
                <td>#{v.id}</td>
                <td>{v.fecha.strftime('%d/%m/%Y %H:%M')}</td>
                <td>RD$ {v.total:.2f}</td>
                <td><span class="pill {'pill-pend' if v.es_fiado else 'pill-ok'}">{'Fiado' if v.es_fiado else 'Pagada'}</span></td>
                <td><a class="btn-link" href="{url_for('recibo', venta_id=v.id)}">Ver Recibo</a></td>
            </tr>"""
      for v in lista
  ) or "<tr><td colspan='5'>Aún no hay ventas registradas.</td></tr>"

  cuerpo = f"""
        <h2>📜 Historial de Ventas</h2>
        <table>
            <tr><th>#</th><th>Fecha</th><th>Total</th><th>Estado</th><th></th></tr>
            {filas}
        </table>
        <br><a class="btn" href="{url_for('nueva_venta')}">+ Nueva Venta</a>
        <br><a class="btn-link volver" href="{url_for('dashboard')}">← Volver</a>
    """
  return render_page("Ventas", cuerpo)


@app.route("/ventas/<int:venta_id>/recibo")
@login_required
def recibo(venta_id):
  venta = Venta.query.filter_by(
      id=venta_id, colmado_id=current_user.colmado_id
  ).first_or_404()

  colmado = Colmado.query.get(current_user.colmado_id)
  detalles = DetalleVenta.query.filter_by(venta_id=venta.id).all()
  cajero = Usuario.query.get(venta.usuario_id)
  fiado = Fiado.query.filter_by(venta_id=venta.id).first() if venta.es_fiado else None

  filas_detalle = "".join(
      f"""<tr>
                <td>{Producto.query.get(d.producto_id).nombre if Producto.query.get(d.producto_id) else '(producto eliminado)'}</td>
                <td style="text-align:center">{d.cantidad}</td>
                <td style="text-align:right">RD$ {d.precio_unitario:.2f}</td>
                <td style="text-align:right">RD$ {d.cantidad * d.precio_unitario:.2f}</td>
            </tr>"""
      for d in detalles
  )

  linea_fiado = ""
  if fiado:
    linea_fiado = f"""
        <p style="text-align:center; color:var(--rojo); font-weight:600;">
            FIADO A: {fiado.nombre_cliente}{' · ' + fiado.telefono_cliente if fiado.telefono_cliente else ''}
        </p>
    """

  texto_whatsapp = f"Recibo {colmado.nombre} - Venta #{venta.id} - Total RD$ {venta.total:.2f} - {venta.fecha.strftime('%d/%m/%Y %H:%M')}"
  import urllib.parse
  whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(texto_whatsapp)}"

  cuerpo = f"""
        <div id="ticket">
            <h2 style="text-align:center; margin-bottom:0;">{colmado.nombre}</h2>
            <p style="text-align:center; color:var(--gris); margin-top:4px;">Recibo de Venta #{venta.id}</p>
            <p style="text-align:center; color:var(--gris); font-size:0.85rem;">{venta.fecha.strftime('%d/%m/%Y %H:%M')} · Atendió: {cajero.nombre if cajero else '-'}</p>
            {linea_fiado}
            <table>
                <tr><th>Producto</th><th style="text-align:center">Cant.</th><th style="text-align:right">Precio</th><th style="text-align:right">Subtotal</th></tr>
                {filas_detalle}
            </table>
            <h3 style="text-align:right; margin-top:16px;">Total: RD$ {venta.total:.2f}</h3>
            <p style="text-align:center; color:var(--gris); font-size:0.85rem;">¡Gracias por su compra!</p>
        </div>

        <div class="no-imprimir">
            <br>
            <a class="btn" href="javascript:window.print()">🖨️ Imprimir</a>
            <a class="btn" href="{whatsapp_url}" target="_blank" style="background:#25D366;">📲 Enviar por WhatsApp</a>
            <br><a class="btn-link volver" href="{url_for('ventas')}">← Volver al historial</a>
        </div>

        <style>
            @media print {{
                .topbar, .no-imprimir {{ display: none !important; }}
                .card {{ box-shadow: none; border: none; }}
                body {{ background: #fff; }}
            }}
        </style>
    """
  return render_page("Recibo", cuerpo)


# --- FIADOS / DEUDAS ---


@app.route("/fiados")
@login_required
def fiados():
  lista = (
      Fiado.query.filter_by(colmado_id=current_user.colmado_id)
      .order_by(Fiado.saldado.asc())
      .all()
  )
  filas = "".join(
      f"""<tr>
                <td>{f.nombre_cliente}</td>
                <td>{f.telefono_cliente or '-'}</td>
                <td>RD$ {f.monto_total:.2f}</td>
                <td>RD$ {f.monto_pagado:.2f}</td>
                <td>RD$ {(f.monto_total - f.monto_pagado):.2f}</td>
                <td><span class="pill {'pill-ok' if f.saldado else 'pill-pend'}">{'Saldado' if f.saldado else 'Pendiente'}</span></td>
                <td>{'' if f.saldado else f'<a class="btn-link" href="{url_for("abonar_fiado", fiado_id=f.id)}">Abonar</a>'}</td>
            </tr>"""
      for f in lista
  ) or "<tr><td colspan='7'>No hay fiados registrados.</td></tr>"

  cuerpo = f"""
        <h2>💳 Fiados / Deudas</h2>
        <table>
            <tr>
                <th>Cliente</th><th>Teléfono</th><th>Total</th>
                <th>Pagado</th><th>Pendiente</th><th>Estado</th><th></th>
            </tr>
            {filas}
        </table>
        <br><a class="btn-link volver" href="{url_for('dashboard')}">← Volver</a>
    """
  return render_page("Fiados", cuerpo)


@app.route("/fiados/<int:fiado_id>/abonar", methods=["GET", "POST"])
@login_required
def abonar_fiado(fiado_id):
  fiado = Fiado.query.filter_by(
      id=fiado_id, colmado_id=current_user.colmado_id
  ).first_or_404()

  if fiado.saldado:
    flash("Esta deuda ya está saldada.", "danger")
    return redirect(url_for("fiados"))

  pendiente = fiado.monto_total - fiado.monto_pagado

  if request.method == "POST":
    monto_str = request.form.get("monto", "0")
    try:
      monto = float(monto_str)
    except ValueError:
      monto = 0

    if monto <= 0:
      flash("El monto debe ser mayor a cero.", "danger")
      return redirect(url_for("abonar_fiado", fiado_id=fiado.id))

    if monto > pendiente:
      flash(f"El abono no puede ser mayor al pendiente (RD$ {pendiente:.2f}).", "danger")
      return redirect(url_for("abonar_fiado", fiado_id=fiado.id))

    fiado.monto_pagado += monto
    if fiado.monto_pagado >= fiado.monto_total:
      fiado.saldado = True

    db.session.commit()
    flash("Abono registrado correctamente.", "success")
    return redirect(url_for("fiados"))

  cuerpo = f"""
        <h2>Abonar a la deuda de {fiado.nombre_cliente}</h2>
        <p>Total: RD$ {fiado.monto_total:.2f} &nbsp;|&nbsp; Pagado: RD$ {fiado.monto_pagado:.2f} &nbsp;|&nbsp; Pendiente: RD$ {pendiente:.2f}</p>
        <form method="POST">
            <input type="number" step="0.01" name="monto" placeholder="Monto a abonar" max="{pendiente}" required>
            <button type="submit">Registrar Abono</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('fiados')}">← Volver</a>
    """
  return render_page("Abonar", cuerpo)


# --- REPORTES ---


@app.route("/reportes")
@login_required
@solo_dueno
def reportes():
  colmado_id = current_user.colmado_id
  hoy = datetime.utcnow().date()
  inicio_hoy = datetime(hoy.year, hoy.month, hoy.day)
  inicio_semana = inicio_hoy - timedelta(days=inicio_hoy.weekday())
  inicio_mes = datetime(hoy.year, hoy.month, 1)

  def total_desde(fecha_inicio):
    resultado = (
        db.session.query(func.coalesce(func.sum(Venta.total), 0.0))
        .filter(Venta.colmado_id == colmado_id, Venta.fecha >= fecha_inicio)
        .scalar()
    )
    return resultado or 0.0

  total_hoy = total_desde(inicio_hoy)
  total_semana = total_desde(inicio_semana)
  total_mes = total_desde(inicio_mes)

  mas_vendidos = (
      Producto.query.filter_by(colmado_id=colmado_id)
      .order_by(Producto.unidades_vendidas.desc())
      .limit(5)
      .all()
  )
  filas_top = "".join(
      f"<tr><td>{p.nombre}</td><td>{p.unidades_vendidas or 0}</td></tr>"
      for p in mas_vendidos
  ) or "<tr><td colspan='2'>Aún no hay ventas</td></tr>"

  UMBRAL_BAJO_STOCK = 10
  bajo_stock = (
      Producto.query.filter(
          Producto.colmado_id == colmado_id,
          Producto.cantidad < UMBRAL_BAJO_STOCK,
      )
      .order_by(Producto.cantidad.asc())
      .all()
  )
  filas_bajo_stock = "".join(
      f"<tr><td>{p.nombre}</td><td>{p.cantidad}</td></tr>" for p in bajo_stock
  ) or "<tr><td colspan='2'>Sin productos en bajo stock</td></tr>"

  cuerpo = f"""
        <h2>📊 Reportes</h2>

        <h3>Ventas</h3>
        <ul class="simple">
            <li>Hoy: <strong>RD$ {total_hoy:.2f}</strong></li>
            <li>Esta semana: <strong>RD$ {total_semana:.2f}</strong></li>
            <li>Este mes: <strong>RD$ {total_mes:.2f}</strong></li>
        </ul>

        <h3>Productos más vendidos</h3>
        <table>
            <tr><th>Producto</th><th>Unidades vendidas</th></tr>
            {filas_top}
        </table>

        <h3>Bajo stock (menos de {UMBRAL_BAJO_STOCK} unidades)</h3>
        <table>
            <tr><th>Producto</th><th>Cantidad</th></tr>
            {filas_bajo_stock}
        </table>

        <br><a class="btn-link volver" href="{url_for('dashboard')}">← Volver</a>
    """
  return render_page("Reportes", cuerpo)


# --- EMPLEADOS (solo dueño) ---


@app.route("/empleados")
@login_required
@solo_dueno
def empleados():
  lista = Usuario.query.filter_by(colmado_id=current_user.colmado_id).all()
  filas = "".join(
      f"""<tr>
                <td>{u.nombre}</td>
                <td>{u.usuario}</td>
                <td><span class="pill {'pill-ok' if u.rol == 'dueno' else 'pill-pend'}">{u.rol}</span></td>
                <td><span class="pill {'pill-ok' if u.activo else 'pill-pend'}">{'Activo' if u.activo else 'Inactivo'}</span></td>
                <td>{'' if u.id == current_user.id else f'<a class="btn-link" href="{url_for("alternar_empleado", usuario_id=u.id)}">{"Desactivar" if u.activo else "Activar"}</a>'}</td>
            </tr>"""
      for u in lista
  )

  cuerpo = f"""
        <h2>👥 Empleados</h2>
        <table>
            <tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Estado</th><th></th></tr>
            {filas}
        </table>
        <br><a class="btn" href="{url_for('nuevo_empleado')}">+ Agregar Empleado</a>
        <br><a class="btn-link volver" href="{url_for('dashboard')}">← Volver</a>
    """
  return render_page("Empleados", cuerpo)


@app.route("/empleados/nuevo", methods=["GET", "POST"])
@login_required
@solo_dueno
def nuevo_empleado():
  if request.method == "POST":
    nombre = request.form.get("nombre")
    usuario = request.form.get("usuario")
    clave = request.form.get("clave")
    rol = request.form.get("rol")

    if not nombre or not usuario or not clave or rol not in ("cajero", "empleado"):
      flash("Todos los campos son obligatorios.", "danger")
      return redirect(url_for("nuevo_empleado"))

    if Usuario.query.filter_by(usuario=usuario).first():
      flash("Ese usuario ya existe, elige otro.", "danger")
      return redirect(url_for("nuevo_empleado"))

    nuevo = Usuario(
        colmado_id=current_user.colmado_id,
        nombre=nombre,
        usuario=usuario,
        clave_hash=generate_password_hash(clave),
        rol=rol,
    )
    db.session.add(nuevo)
    db.session.commit()
    flash("Empleado agregado correctamente.", "success")
    return redirect(url_for("empleados"))

  cuerpo = f"""
        <h2>➕ Nuevo Empleado</h2>
        <form method="POST">
            <input type="text" name="nombre" placeholder="Nombre completo" required>
            <input type="text" name="usuario" placeholder="Usuario para iniciar sesión" required>
            <input type="password" name="clave" placeholder="Contraseña" required>
            <label><input type="radio" name="rol" value="cajero" checked> Cajero (vender y consultar)</label>
            <label><input type="radio" name="rol" value="empleado"> Empleado básico</label>
            <button type="submit">Guardar</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('empleados')}">← Volver</a>
    """
  return render_page("Nuevo Empleado", cuerpo)


@app.route("/empleados/<int:usuario_id>/alternar")
@login_required
@solo_dueno
def alternar_empleado(usuario_id):
  usuario_obj = Usuario.query.filter_by(
      id=usuario_id, colmado_id=current_user.colmado_id
  ).first_or_404()

  if usuario_obj.id == current_user.id:
    flash("No puedes desactivar tu propia cuenta.", "danger")
    return redirect(url_for("empleados"))

  usuario_obj.activo = not usuario_obj.activo
  db.session.commit()
  flash("Estado del empleado actualizado.", "success")
  return redirect(url_for("empleados"))


# --- SUPER-ADMIN (tú, el creador del sistema) ---
# Entra por el mismo /login de siempre, con un usuario que tenga rol='superadmin'.


@app.route("/superadmin/panel")
@login_required
@superadmin_requerido
def superadmin_panel():
  colmados = (
      Colmado.query.filter(Colmado.estado != "eliminado")
      .order_by(Colmado.fecha_registro.desc())
      .all()
  )

  def fila(c):
    dueno = c.dueno
    plan_nombre = c.plan.nombre if c.plan else "Sin plan"
    vence = c.membresia_vence.strftime('%d/%m/%Y') if c.membresia_vence else '-'
    return f"""<tr>
                <td><a class="btn-link" href="{url_for('superadmin_colmado', colmado_id=c.id)}">{c.nombre}</a></td>
                <td>{dueno.nombre if dueno else '-'}</td>
                <td>{plan_nombre}</td>
                <td>{vence}</td>
                <td>{estado_pill(c.estado)}</td>
            </tr>"""

  filas = "".join(fila(c) for c in colmados) or "<tr><td colspan='5'>Aún no hay colmados registrados.</td></tr>"

  cuerpo = f"""
        <h2>🔐 Panel de Super-Administrador</h2>
        <p style="color:var(--gris);">Todos los colmados registrados en el sistema.</p>
        <table>
            <tr><th>Colmado</th><th>Dueño</th><th>Plan</th><th>Vence</th><th>Estado</th></tr>
            {filas}
        </table>
        <br>
        <a class="btn" href="{url_for('superadmin_nuevo_colmado')}">+ Nuevo Colmado</a>
        <a class="btn" href="{url_for('superadmin_planes')}" style="background:var(--gris);">📋 Planes</a>
        <br><a class="btn-link volver" href="{url_for('logout')}">Cerrar sesión</a>
    """
  return render_page("Panel Super-Admin", cuerpo, mostrar_nav=True)


@app.route("/superadmin/colmados/nuevo", methods=["GET", "POST"])
@login_required
@superadmin_requerido
def superadmin_nuevo_colmado():
  planes = Plan.query.filter_by(activo=True).all()

  if request.method == "POST":
    nombre_colmado = request.form.get("nombre_colmado")
    nombre_dueno = request.form.get("nombre_dueno")
    usuario = request.form.get("usuario")
    clave = request.form.get("clave")
    plan_id = request.form.get("plan_id") or None

    if not nombre_colmado or not nombre_dueno or not usuario or not clave:
      flash("Todos los campos son obligatorios.", "danger")
      return redirect(url_for("superadmin_nuevo_colmado"))

    if Usuario.query.filter_by(usuario=usuario).first():
      flash("Ese usuario ya existe, elige otro.", "danger")
      return redirect(url_for("superadmin_nuevo_colmado"))

    plan = Plan.query.get(int(plan_id)) if plan_id else None
    dias = plan.duracion_dias if plan else 30

    nuevo_colmado = Colmado(
        nombre=nombre_colmado,
        plan_id=plan.id if plan else None,
        membresia_vence=datetime.utcnow() + timedelta(days=dias),
        estado="activo",
    )
    db.session.add(nuevo_colmado)
    db.session.commit()

    nuevo_dueno = Usuario(
        colmado_id=nuevo_colmado.id,
        nombre=nombre_dueno,
        usuario=usuario,
        clave_hash=generate_password_hash(clave),
        rol="dueno",
    )
    db.session.add(nuevo_dueno)
    db.session.commit()

    flash(f"Colmado '{nombre_colmado}' creado correctamente.", "success")
    return redirect(url_for("superadmin_panel"))

  opciones_plan = "".join(
      f'<option value="{p.id}">{p.nombre} (RD$ {p.precio:.2f} / {p.duracion_dias} días)</option>'
      for p in planes
  ) or '<option value="">Sin planes creados</option>'

  cuerpo = f"""
        <h2>➕ Nuevo Colmado</h2>
        <form method="POST">
            <input type="text" name="nombre_colmado" placeholder="Nombre del Colmado" required>
            <input type="text" name="nombre_dueno" placeholder="Nombre del Dueño" required>
            <input type="text" name="usuario" placeholder="Usuario del dueño" required>
            <input type="password" name="clave" placeholder="Contraseña del dueño" required>
            <label>Plan: <select name="plan_id">{opciones_plan}</select></label>
            <button type="submit">Crear Colmado</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('superadmin_panel')}">← Volver</a>
    """
  return render_page("Nuevo Colmado", cuerpo)


@app.route("/superadmin/colmados/<int:colmado_id>")
@login_required
@superadmin_requerido
def superadmin_colmado(colmado_id):
  colmado = Colmado.query.get_or_404(colmado_id)
  usuarios = Usuario.query.filter_by(colmado_id=colmado.id).all()
  planes = Plan.query.filter_by(activo=True).all()

  filas_usuarios = "".join(
      f"""<tr>
                <td>{u.nombre}</td><td>{u.usuario}</td>
                <td><span class="pill pill-ok">{u.rol}</span></td>
                <td><span class="pill {'pill-ok' if u.activo else 'pill-pend'}">{'Activo' if u.activo else 'Inactivo'}</span></td>
            </tr>"""
      for u in usuarios
  ) or "<tr><td colspan='4'>Sin usuarios.</td></tr>"

  opciones_plan = "".join(
      f'<option value="{p.id}" {"selected" if colmado.plan_id == p.id else ""}>{p.nombre} (RD$ {p.precio:.2f} / {p.duracion_dias} días)</option>'
      for p in planes
  )

  vence_valor = colmado.membresia_vence.strftime('%Y-%m-%d') if colmado.membresia_vence else ""

  acciones_estado = ""
  if colmado.estado == "activo":
    acciones_estado = f'<a class="btn-link" href="{url_for("superadmin_estado_colmado", colmado_id=colmado.id, accion="suspender")}">⏸️ Suspender</a>'
  elif colmado.estado == "suspendido":
    acciones_estado = f'<a class="btn-link" href="{url_for("superadmin_estado_colmado", colmado_id=colmado.id, accion="activar")}">▶️ Activar</a>'

  cuerpo = f"""
        <h2>🏪 {colmado.nombre}</h2>
        <p>{estado_pill(colmado.estado)} · Dueño: {colmado.dueno.nombre if colmado.dueno else '-'}</p>

        <h3>Editar colmado</h3>
        <form method="POST" action="{url_for('superadmin_editar_colmado', colmado_id=colmado.id)}">
            <input type="text" name="nombre" value="{colmado.nombre}" required>
            <button type="submit">Guardar Nombre</button>
        </form>

        <h3>Plan y vencimiento</h3>
        <form method="POST" action="{url_for('superadmin_plan_colmado', colmado_id=colmado.id)}">
            <label>Plan: <select name="plan_id">{opciones_plan}</select></label>
            <label>Vence: <input type="date" name="vence" value="{vence_valor}"></label>
            <button type="submit">Actualizar Plan</button>
        </form>
        <p>
            <a class="btn-link" href="{url_for('superadmin_renovar', colmado_id=colmado.id, dias=30)}">+30 días</a> ·
            <a class="btn-link" href="{url_for('superadmin_renovar', colmado_id=colmado.id, dias=7)}">+7 días</a>
        </p>

        <h3>Estado</h3>
        <p>{acciones_estado} ·
           <a class="btn-link" href="{url_for('superadmin_estado_colmado', colmado_id=colmado.id, accion='eliminar')}"
              onclick="return confirm('¿Eliminar el colmado {colmado.nombre}? Esto lo desactiva por completo.')">🗑️ Eliminar</a>
        </p>

        <h3>Usuarios (dueño / empleados)</h3>
        <table>
            <tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Estado</th></tr>
            {filas_usuarios}
        </table>

        <br><a class="btn-link volver" href="{url_for('superadmin_panel')}">← Volver al panel</a>
    """
  return render_page(f"Colmado · {colmado.nombre}", cuerpo)


@app.route("/superadmin/colmados/<int:colmado_id>/editar", methods=["POST"])
@login_required
@superadmin_requerido
def superadmin_editar_colmado(colmado_id):
  colmado = Colmado.query.get_or_404(colmado_id)
  nombre = request.form.get("nombre")
  if nombre:
    colmado.nombre = nombre
    db.session.commit()
    flash("Colmado actualizado.", "success")
  return redirect(url_for("superadmin_colmado", colmado_id=colmado.id))


@app.route("/superadmin/colmados/<int:colmado_id>/plan", methods=["POST"])
@login_required
@superadmin_requerido
def superadmin_plan_colmado(colmado_id):
  colmado = Colmado.query.get_or_404(colmado_id)
  plan_id = request.form.get("plan_id")
  vence = request.form.get("vence")

  colmado.plan_id = int(plan_id) if plan_id else None
  if vence:
    colmado.membresia_vence = datetime.strptime(vence, "%Y-%m-%d")

  db.session.commit()
  flash("Plan y vencimiento actualizados.", "success")
  return redirect(url_for("superadmin_colmado", colmado_id=colmado.id))


@app.route("/superadmin/colmados/<int:colmado_id>/renovar/<int:dias>")
@login_required
@superadmin_requerido
def superadmin_renovar(colmado_id, dias):
  colmado = Colmado.query.get_or_404(colmado_id)
  base = colmado.membresia_vence if colmado.membresia_vence and colmado.membresia_vence > datetime.utcnow() else datetime.utcnow()
  colmado.membresia_vence = base + timedelta(days=dias)
  colmado.estado = "activo"
  colmado.membresia_activa = True

  pago = PagoMembresia(
      colmado_id=colmado.id,
      dias_agregados=dias,
      nota=f"Renovación manual de {dias} días vía panel super-admin",
  )
  db.session.add(pago)
  db.session.commit()

  flash(f"Membresía de '{colmado.nombre}' extendida {dias} días.", "success")
  return redirect(url_for("superadmin_colmado", colmado_id=colmado.id))


@app.route("/superadmin/colmados/<int:colmado_id>/estado/<accion>")
@login_required
@superadmin_requerido
def superadmin_estado_colmado(colmado_id, accion):
  colmado = Colmado.query.get_or_404(colmado_id)

  if accion == "activar":
    colmado.activar()
    flash(f"'{colmado.nombre}' activado.", "success")
  elif accion == "suspender":
    colmado.suspender()
    flash(f"'{colmado.nombre}' suspendido.", "success")
  elif accion == "eliminar":
    colmado.eliminar()
    flash(f"'{colmado.nombre}' eliminado.", "success")
  else:
    flash("Acción no reconocida.", "danger")

  db.session.commit()
  return redirect(url_for("superadmin_panel"))


@app.route("/superadmin/planes")
@login_required
@superadmin_requerido
def superadmin_planes():
  planes = Plan.query.all()
  filas = "".join(
      f"""<tr>
                <td>{p.nombre}</td><td>RD$ {p.precio:.2f}</td><td>{p.duracion_dias} días</td>
                <td><span class="pill {'pill-ok' if p.activo else 'pill-pend'}">{'Disponible' if p.activo else 'Descontinuado'}</span></td>
                <td><a class="btn-link" href="{url_for('superadmin_alternar_plan', plan_id=p.id)}">{'Descontinuar' if p.activo else 'Reactivar'}</a></td>
            </tr>"""
      for p in planes
  ) or "<tr><td colspan='5'>Aún no hay planes creados.</td></tr>"

  cuerpo = f"""
        <h2>📋 Planes</h2>
        <table>
            <tr><th>Nombre</th><th>Precio</th><th>Duración</th><th>Estado</th><th></th></tr>
            {filas}
        </table>
        <h3>Nuevo Plan</h3>
        <form method="POST" action="{url_for('superadmin_nuevo_plan')}">
            <input type="text" name="nombre" placeholder="Nombre del plan" required>
            <input type="number" step="0.01" name="precio" placeholder="Precio" required>
            <input type="number" name="duracion_dias" placeholder="Duración en días" value="30" required>
            <button type="submit">Crear Plan</button>
        </form>
        <br><a class="btn-link volver" href="{url_for('superadmin_panel')}">← Volver</a>
    """
  return render_page("Planes", cuerpo)


@app.route("/superadmin/planes/nuevo", methods=["POST"])
@login_required
@superadmin_requerido
def superadmin_nuevo_plan():
  nombre = request.form.get("nombre")
  precio = request.form.get("precio")
  duracion_dias = request.form.get("duracion_dias")

  if not nombre or not precio or not duracion_dias:
    flash("Todos los campos son obligatorios.", "danger")
    return redirect(url_for("superadmin_planes"))

  nuevo = Plan(nombre=nombre, precio=float(precio), duracion_dias=int(duracion_dias), activo=True)
  db.session.add(nuevo)
  db.session.commit()
  flash("Plan creado correctamente.", "success")
  return redirect(url_for("superadmin_planes"))


@app.route("/superadmin/planes/<int:plan_id>/alternar")
@login_required
@superadmin_requerido
def superadmin_alternar_plan(plan_id):
  plan = Plan.query.get_or_404(plan_id)
  plan.activo = not plan.activo
  db.session.commit()
  flash("Estado del plan actualizado.", "success")
  return redirect(url_for("superadmin_planes"))


with app.app_context():
  db.create_all()


if __name__ == "__main__":
  print("✅ Conexión exitosa. Tablas creadas en la base de datos.")
  app.run(debug=True)