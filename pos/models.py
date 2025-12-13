from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal


class Venta(models.Model):
    """
    Modelo para registrar ventas realizadas en el punto de venta.
    """
    ESTADO_CHOICES = [
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('DEVUELTA', 'Devuelta'),
    ]

    METODO_PAGO_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
    ]

    # Identificación
    numero_ticket = models.CharField(max_length=20, unique=True, editable=False, db_index=True)

    # Relaciones
    cajero = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='ventas_realizadas'
    )

    # Montos
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    descuento_monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    # Pago
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        default='EFECTIVO'
    )
    monto_recibido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    cambio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='COMPLETADA'
    )

    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    # Notas
    notas = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        indexes = [
            models.Index(fields=['-fecha_creacion']),
            models.Index(fields=['numero_ticket']),
            models.Index(fields=['cajero']),
        ]

    def __str__(self):
        return f"Ticket {self.numero_ticket} - ${self.total}"

    def save(self, *args, **kwargs):
        if not self.numero_ticket:
            self.numero_ticket = self.generar_numero_ticket()
        super().save(*args, **kwargs)

    def generar_numero_ticket(self):
        """
        Genera un número de ticket único con formato YYYYMMDD-XXXXX
        Ejemplo: 20251214-00001
        """
        fecha = timezone.now().strftime('%Y%m%d')

        # Buscar último ticket del día
        ultimo_ticket = Venta.objects.filter(
            numero_ticket__startswith=fecha
        ).order_by('-numero_ticket').first()

        if ultimo_ticket:
            # Extraer secuencia y incrementar
            ultimo_numero = int(ultimo_ticket.numero_ticket.split('-')[1])
            nuevo_numero = ultimo_numero + 1
        else:
            # Primer ticket del día
            nuevo_numero = 1

        return f"{fecha}-{nuevo_numero:05d}"

    def calcular_totales(self):
        """
        Calcula subtotal, descuento y total basado en los detalles de la venta.
        """
        self.subtotal = sum(
            detalle.subtotal for detalle in self.detalles.all()
        )
        self.descuento_monto = (self.subtotal * self.descuento_porcentaje / 100)
        self.total = self.subtotal - self.descuento_monto
        return self.total

    def puede_ser_devuelta(self):
        """
        Verifica si la venta puede ser devuelta (dentro de 30 días y estado COMPLETADA).
        """
        from datetime import timedelta

        if self.estado != 'COMPLETADA':
            return False

        limite_devolucion = self.fecha_creacion + timedelta(days=30)
        return timezone.now() <= limite_devolucion


class DetalleVenta(models.Model):
    """
    Modelo para los detalles (productos) de cada venta.
    """
    # Relaciones
    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name='detalles'
    )
    perfume = models.ForeignKey(
        'perfumes.Perfume',
        on_delete=models.PROTECT
    )

    # Información del producto al momento de la venta (snapshot)
    nombre_producto = models.CharField(max_length=200)
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    # Cantidad y descuentos
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    descuento_monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    # Totales
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'
        ordering = ['id']

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto} - ${self.subtotal}"

    def calcular_subtotal(self):
        """
        Calcula el subtotal considerando cantidad y descuentos.
        """
        base = self.precio_unitario * self.cantidad
        self.descuento_monto = (base * self.descuento_porcentaje / 100)
        self.subtotal = base - self.descuento_monto
        return self.subtotal

    def save(self, *args, **kwargs):
        # Guardar snapshot del producto
        if not self.nombre_producto:
            self.nombre_producto = str(self.perfume)
        if not self.precio_unitario:
            self.precio_unitario = self.perfume.precio

        # Calcular subtotal
        self.calcular_subtotal()

        super().save(*args, **kwargs)


class MovimientoInventario(models.Model):
    """
    Modelo para registrar todos los movimientos de inventario.
    Mantiene un historial completo de entradas y salidas de stock.
    """
    TIPO_MOVIMIENTO_CHOICES = [
        ('VENTA', 'Venta'),
        ('DEVOLUCION', 'Devolución'),
        ('CANCELACION', 'Cancelación'),
        ('AJUSTE_MANUAL', 'Ajuste Manual'),
    ]

    # Relaciones
    perfume = models.ForeignKey(
        'perfumes.Perfume',
        on_delete=models.PROTECT,
        related_name='movimientos'
    )
    venta = models.ForeignKey(
        Venta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    # Información del movimiento
    tipo_movimiento = models.CharField(
        max_length=20,
        choices=TIPO_MOVIMIENTO_CHOICES,
        db_index=True
    )
    cantidad = models.IntegerField()  # Positivo para entrada, negativo para salida
    stock_anterior = models.IntegerField(validators=[MinValueValidator(0)])
    stock_nuevo = models.IntegerField(validators=[MinValueValidator(0)])

    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_index=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        indexes = [
            models.Index(fields=['-fecha_creacion']),
            models.Index(fields=['perfume']),
            models.Index(fields=['tipo_movimiento']),
        ]

    def __str__(self):
        return f"{self.tipo_movimiento} - {self.perfume.nombre} ({self.cantidad})"


class VentaTemporal(models.Model):
    """
    Almacena temporalmente los productos agregados por el cajero
    antes de completar la venta. Similar a un carrito de compras
    pero específico para punto de venta.
    """
    # Relaciones
    cajero = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    perfume = models.ForeignKey(
        'perfumes.Perfume',
        on_delete=models.CASCADE
    )

    # Detalles del item
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Timestamps
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Venta Temporal'
        verbose_name_plural = 'Ventas Temporales'
        ordering = ['fecha_agregado']
        unique_together = ['cajero', 'perfume']  # Un producto por sesión de cajero

    def __str__(self):
        return f"{self.cajero.username} - {self.cantidad}x {self.perfume.nombre}"

    def calcular_subtotal(self):
        """
        Calcula el subtotal del item considerando cantidad y descuento.
        """
        base = self.precio_unitario * self.cantidad
        descuento = base * self.descuento_porcentaje / 100
        return base - descuento
