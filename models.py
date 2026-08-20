from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()


# --- PERMISOS DELEGABLES ---
# Estos son los permisos que el DUEÑO puede activar/desactivar por empleado.
# El dueño siempre tiene TODOS los permisos automáticamente (ver Usuario.tiene_permiso).
# Agregar/eliminar empleados y configuración del colmado NUNCA son delegables:
# esas rutas siguen protegidas solo para el rol 'dueno'.
PERMISOS_DISPONIBLES = {
    "productos": "Agregar, editar y eliminar productos (incluye cambiar precios)",
    "reportes": "Ver reportes generales del negocio",
    "ganancias": "Ver ganancias y totales del negocio",
    "caja_completa": "Ver y hacer el cuadre completo de caja",
}


class Plan(db.Model):
    """Planes de membresía que el superadmin puede crear y asignar a un colmado."""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)          # ej. "Básico", "Pro"
    precio = db.Column(db.Float, nullable=False)
    duracion_dias = db.Column(db.Integer, nullable=False, default=30)
    activo = db.Column(db.Boolean, default=True)                # si el plan sigue disponible para asignar

    colmados = db.relationship('Colmado', backref='plan', lazy=True)


class Colmado(db.Model):
    """Cada colmado que usa el sistema (esto lo hace multi-cliente)."""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # Plan asignado
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=True)

    # Control de membresía (esto lo maneja el creador del sistema)
    membresia_activa = db.Column(db.Boolean, default=True)
    membresia_vence = db.Column(db.DateTime, nullable=False)

    # Estado general del colmado, controlado por el superadmin
    # Valores: 'activo', 'suspendido', 'eliminado'
    estado = db.Column(db.String(20), nullable=False, default='activo')

    # Configuración propia del colmado (moneda, logo, nombre del negocio en factura, etc.)
    configuracion = db.Column(db.JSON, default=dict)

    # Relaciones
    usuarios = db.relationship('Usuario', backref='colmado', lazy=True)

    @property
    def dueno(self):
        """El usuario con rol 'dueno' dentro de este colmado."""
        return next((u for u in self.usuarios if u.rol == 'dueno'), None)

    def renovar_membresia(self, dias=None):
        """Extiende la fecha de vencimiento. Si no se pasan días, usa la duración del plan asignado."""
        dias = dias or (self.plan.duracion_dias if self.plan else 30)
        base = self.membresia_vence if self.membresia_vence and self.membresia_vence > datetime.utcnow() else datetime.utcnow()
        self.membresia_vence = base + timedelta(days=dias)
        self.membresia_activa = True

    def suspender(self):
        self.estado = 'suspendido'
        self.membresia_activa = False

    def activar(self):
        self.estado = 'activo'
        self.membresia_activa = True

    def eliminar(self):
        """Borrado lógico: no se elimina de la base de datos, solo se marca."""
        self.estado = 'eliminado'
        self.membresia_activa = False


class Usuario(db.Model, UserMixin):
    """Usuarios del sistema: superadmin, dueño, cajero o empleado básico."""
    id = db.Column(db.Integer, primary_key=True)

    # nullable=True porque el superadmin no pertenece a ningún colmado
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=True)

    nombre = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    clave_hash = db.Column(db.String(255), nullable=False)  # nunca guardamos la clave en texto plano

    # Roles: 'superadmin', 'dueno', 'cajero', 'empleado'
    rol = db.Column(db.String(20), nullable=False, default='empleado')

    activo = db.Column(db.Boolean, default=True)

    # Permisos delegables que el dueño activa/desactiva individualmente.
    # Ejemplo: {"productos": true, "reportes": false, "ganancias": false, "caja_completa": true}
    # Claves ausentes se consideran False. El dueño ignora esto porque tiene_permiso()
    # le devuelve True para todo automáticamente.
    permisos = db.Column(db.JSON, default=dict)

    @property
    def es_superadmin(self):
        return self.rol == 'superadmin'

    def tiene_permiso(self, clave):
        """True si el usuario puede usar la función 'clave'.
        El dueño siempre tiene acceso total. Cajero/empleado dependen de sus permisos."""
        if self.rol == 'dueno':
            return True
        return bool((self.permisos or {}).get(clave, False))


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

    # Dinero recibido en efectivo y cambio devuelto (solo aplica a ventas NO fiadas).
    # Si el cajero no registra el efectivo recibido, quedan en None.
    efectivo_recibido = db.Column(db.Float, nullable=True)
    cambio_devuelto = db.Column(db.Float, nullable=True)

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


class MovimientoCaja(db.Model):
    """Entradas y salidas de dinero de la caja, fuera de las ventas normales.
    Ej: entrada de capital, salida para comprar algo, pago de un gasto, etc.
    También los abonos de fiado se registran aquí como tipo 'entrada'."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    tipo = db.Column(db.String(10), nullable=False)  # 'entrada' o 'salida'
    monto = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(200), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


class CuadreCaja(db.Model):
    """(Histórica, ya no se usa desde la Fase 1 — reemplazada por CierreCaja.
    Se deja aquí sin borrar para no perder datos viejos ni romper la tabla existente.)
    Cuadre de caja: compara lo que el sistema espera en efectivo contra lo
    que el usuario contó físicamente, y guarda la diferencia."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    efectivo_esperado = db.Column(db.Float, nullable=False)
    efectivo_contado = db.Column(db.Float, nullable=False)
    diferencia = db.Column(db.Float, nullable=False)  # contado - esperado
    nota = db.Column(db.String(200))


class CierreCaja(db.Model):
    """NUEVO — Fase 1. Cierre formal del día: una sola vez por colmado y por
    fecha (ver UniqueConstraint). Mientras exista un registro aquí para hoy,
    el sistema bloquea nuevas ventas hasta que el dueño lo reabra."""
    __tablename__ = "cierre_caja"

    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)  # el día calendario que se está cerrando
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    efectivo_esperado = db.Column(db.Float, nullable=False)
    efectivo_contado = db.Column(db.Float, nullable=False)
    diferencia = db.Column(db.Float, nullable=False)
    nota = db.Column(db.Text)
    fecha_cierre = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('colmado_id', 'fecha', name='uq_cierre_colmado_fecha'),
    )


class Pedido(db.Model):
    """Pedido de delivery. Puede ligarse a una venta ya registrada, o crearse
    aparte y cobrarse al momento de la entrega."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'), nullable=True)
    repartidor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

    nombre_cliente = db.Column(db.String(100), nullable=False)
    telefono_cliente = db.Column(db.String(20))
    direccion = db.Column(db.String(250), nullable=False)
    nota = db.Column(db.String(250))

    # Estados: 'pendiente', 'en_camino', 'entregado'
    estado = db.Column(db.String(20), nullable=False, default='pendiente')

    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_entregado = db.Column(db.DateTime, nullable=True)


class PagoMembresia(db.Model):
    """Historial de pagos/renovaciones de membresía por colmado (lo maneja el creador del sistema)."""
    id = db.Column(db.Integer, primary_key=True)
    colmado_id = db.Column(db.Integer, db.ForeignKey('colmado.id'), nullable=False)

    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    dias_agregados = db.Column(db.Integer, nullable=False)  # ej. 30 días por un pago mensual
    monto = db.Column(db.Float)  # opcional, por si quieres llevar cuánto te pagaron
    nota = db.Column(db.String(200))  # ej. "Pago mensual agosto" o "Extensión de cortesía"