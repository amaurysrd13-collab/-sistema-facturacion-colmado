from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class Colmado(db.Model):
    """Cada colmado que usa el sistema (esto lo hace multi-cliente)."""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # Control de membresía (esto lo maneja el creador del sistema)
    membresia_activa = db.Column(db.Boolean, default=True)
    membresia_vence = db.Column(db.DateTime, nullable=False)

    # Relaciones
    usuarios = db.relationship('Usuario', backref='colmado', lazy=True)


class Usuario(db.Model, UserMixin):
    """Usuarios del sistema: dueño, cajero o empleado básico."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)

    nombre = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    clave_hash = db.Column(db.String(255), nullable=False)  # nunca guardamos la clave en texto plano

    # Roles: 'dueno', 'cajero', 'empleado'
    rol = db.Column(db.String(20), nullable=False, default='empleado')

    activo = db.Column(db.Boolean, default=True)


class Producto(db.Model):
    """Productos del inventario, cada uno pertenece a un colmado."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)

    nombre = db.Column(db.String(150), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=0)

    # Para saber qué se vende más, contamos cuántas unidades se han vendido en total
    unidades_vendidas = db.Column(db.Integer, default=0)


class Venta(db.Model):
    """Cada factura generada."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)

    # Si la venta fue fiada (a crédito) o pagada de una vez
    es_fiado = db.Column(db.Boolean, default=False)

    detalles = db.relationship('DetalleVenta', backref='venta', lazy=True)


class DetalleVenta(db.Model):
    """Cada producto dentro de una factura (una factura puede tener varios productos)."""
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)

    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)  # guardamos el precio al momento de vender


class Fiado(db.Model):
    """Deudas de clientes, con soporte para abonos parciales."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'), nullable=False)

    nombre_cliente = db.Column(db.String(100), nullable=False)
    telefono_cliente = db.Column(db.String(20))

    monto_total = db.Column(db.Float, nullable=False)
    monto_pagado = db.Column(db.Float, default=0.0)

    saldado = db.Column(db.Boolean, default=False)


class PagoMembresia(db.Model):
    """Historial de pagos/renovaciones de membresía por colmado (lo maneja el creador del sistema)."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)

    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    dias_agregados = db.Column(db.Integer, nullable=False)  # ej. 30 días por un pago mensual
    monto = db.Column(db.Float)  # opcional, por si quieres llevar cuánto te pagaron
    nota = db.Column(db.String(200))  # ej. "Pago mensual agosto" o "Extensión de cortesía"