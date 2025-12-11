from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from django.contrib.auth.models import User
from decimal import Decimal


class Product(models.Model):
    """
    Modelo de producto generalizado (migrado desde Perfume).
    Representa cualquier producto vendible en el sistema POS.
    """

    CATEGORIA_CHOICES = [
        ('EDT', 'Eau de Toilette'),
        ('EDP', 'Eau de Parfum'),
        ('EDC', 'Eau de Cologne'),
        ('PARFUM', 'Parfum'),
        ('SPLASH', 'Splash'),
        ('ACCESORIO', 'Accesorio'),
        ('OTRO', 'Otro'),
    ]

    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('U', 'Unisex'),
    ]

    codigo_barras = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código de Barras',
        help_text='Código de barras único del producto',
        validators=[
            RegexValidator(
                regex=r'^[0-9A-Za-z\-]+$',
                message='El código de barras solo puede contener números, letras y guiones'
            )
        ],
        db_index=True
    )

    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        db_index=True
    )

    marca = models.CharField(
        max_length=100,
        verbose_name='Marca',
        blank=True,
        db_index=True
    )

    descripcion = models.TextField(
        verbose_name='Descripción',
        blank=True
    )

    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio',
        help_text='Precio de venta unitario'
    )

    stock_actual = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Stock Actual',
        help_text='Cantidad actual en inventario'
    )

    stock_minimo = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        verbose_name='Stock Mínimo',
        help_text='Cantidad mínima antes de alerta de reabastecimiento'
    )

    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        verbose_name='Categoría',
        db_index=True
    )

    volumen = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Volumen (ml)',
        help_text='Volumen en mililitros',
        blank=True,
        null=True
    )

    genero = models.CharField(
        max_length=1,
        choices=GENERO_CHOICES,
        verbose_name='Género',
        blank=True
    )

    imagen = models.ImageField(
        upload_to='productos/',
        blank=True,
        null=True,
        verbose_name='Imagen'
    )

    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Producto disponible para venta'
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['codigo_barras']),
            models.Index(fields=['nombre']),
            models.Index(fields=['categoria', 'activo']),
        ]

    def __str__(self):
        if self.volumen:
            return f"{self.nombre} - {self.marca} ({self.volumen}ml) [{self.codigo_barras}]"
        return f"{self.nombre} - {self.marca} [{self.codigo_barras}]"

    @property
    def disponible(self):
        """Verifica si el producto está disponible para venta"""
        return self.activo and self.stock_actual > 0

    @property
    def requiere_reabastecimiento(self):
        """Verifica si el stock está por debajo del mínimo"""
        return self.stock_actual <= self.stock_minimo

    @property
    def valor_inventario(self):
        """Calcula el valor total del inventario actual"""
        return self.stock_actual * self.precio


class UserProfile(models.Model):
    """
    Perfil de usuario extendido para el sistema POS.
    Agrega roles y turnos a los usuarios del sistema.
    """

    ROL_CHOICES = [
        ('CAJERO', 'Cajero'),
        ('ADMINISTRADOR', 'Administrador'),
        ('SUPERVISOR', 'Supervisor'),
    ]

    TURNO_CHOICES = [
        ('MATUTINO', 'Matutino (8:00 - 15:00)'),
        ('VESPERTINO', 'Vespertino (15:00 - 22:00)'),
        ('NOCTURNO', 'Nocturno (22:00 - 8:00)'),
        ('COMPLETO', 'Tiempo Completo'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Usuario'
    )

    rol = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        default='CAJERO',
        verbose_name='Rol',
        help_text='Rol del usuario en el sistema POS'
    )

    turno = models.CharField(
        max_length=20,
        choices=TURNO_CHOICES,
        default='COMPLETO',
        verbose_name='Turno',
        help_text='Turno de trabajo asignado'
    )

    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Usuario activo en el sistema POS'
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_rol_display()}"

    @property
    def nombre_completo(self):
        """Retorna el nombre completo del usuario"""
        return self.user.get_full_name() or self.user.username


class Inventory(models.Model):
    """
    Modelo de inventario para rastrear movimientos de stock.
    Registra todas las entradas, salidas y ajustes de productos.
    """

    TIPO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('AJUSTE', 'Ajuste'),
        ('DEVOLUCION', 'Devolución'),
    ]

    producto = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='movimientos',
        verbose_name='Producto'
    )

    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad',
        help_text='Cantidad del movimiento (siempre positiva)'
    )

    tipo = models.CharField(
        max_length=15,
        choices=TIPO_CHOICES,
        verbose_name='Tipo de Movimiento',
        db_index=True
    )

    motivo = models.TextField(
        verbose_name='Motivo',
        help_text='Descripción del motivo del movimiento'
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='movimientos_inventario',
        verbose_name='Usuario',
        help_text='Usuario que registró el movimiento'
    )

    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora',
        db_index=True
    )

    stock_anterior = models.IntegerField(
        verbose_name='Stock Anterior',
        help_text='Stock antes del movimiento'
    )

    stock_nuevo = models.IntegerField(
        verbose_name='Stock Nuevo',
        help_text='Stock después del movimiento'
    )

    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['producto', '-fecha']),
            models.Index(fields=['tipo', '-fecha']),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.nombre} ({self.cantidad}) - {self.fecha.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        """
        Sobrescribe save para actualizar automáticamente el stock del producto.
        """
        if not self.pk:
            self.stock_anterior = self.producto.stock_actual

            if self.tipo in ['ENTRADA', 'DEVOLUCION']:
                self.producto.stock_actual += self.cantidad
            elif self.tipo in ['SALIDA', 'AJUSTE']:
                self.producto.stock_actual -= self.cantidad
                if self.producto.stock_actual < 0:
                    raise ValueError('El stock no puede ser negativo')

            self.stock_nuevo = self.producto.stock_actual
            self.producto.save()

        super().save(*args, **kwargs)


class Sales(models.Model):
    """
    Modelo de ventas para registrar transacciones POS.
    Representa una venta completa con todos sus detalles.
    """

    METODO_PAGO_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('MIXTO', 'Mixto'),
    ]

    ESTADO_CHOICES = [
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
        ('PENDIENTE', 'Pendiente'),
    ]

    numero_ticket = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Número de Ticket',
        help_text='Número único de ticket generado automáticamente',
        db_index=True
    )

    fecha_hora = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora',
        db_index=True
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Total',
        help_text='Monto total de la venta'
    )

    metodo_pago = models.CharField(
        max_length=20,
        choices=METODO_PAGO_CHOICES,
        verbose_name='Método de Pago',
        db_index=True
    )

    cajero = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='ventas_realizadas',
        verbose_name='Cajero',
        help_text='Usuario que realizó la venta'
    )

    estado = models.CharField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default='COMPLETADA',
        verbose_name='Estado',
        db_index=True
    )

    descuento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Descuento',
        help_text='Descuento aplicado a la venta'
    )

    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
        help_text='Notas adicionales sobre la venta'
    )

    fecha_cancelacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Cancelación'
    )

    motivo_cancelacion = models.TextField(
        blank=True,
        verbose_name='Motivo de Cancelación'
    )

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora']),
            models.Index(fields=['numero_ticket']),
            models.Index(fields=['estado', '-fecha_hora']),
            models.Index(fields=['cajero', '-fecha_hora']),
        ]

    def __str__(self):
        return f"Ticket {self.numero_ticket} - ${self.total} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        """
        Genera número de ticket automático si no existe.
        """
        if not self.numero_ticket:
            from django.utils import timezone
            fecha = timezone.now().strftime('%Y%m%d')
            ultimo = Sales.objects.filter(
                numero_ticket__startswith=fecha
            ).order_by('-numero_ticket').first()

            if ultimo:
                ultimo_num = int(ultimo.numero_ticket.split('-')[1])
                nuevo_num = ultimo_num + 1
            else:
                nuevo_num = 1

            self.numero_ticket = f"{fecha}-{nuevo_num:04d}"

        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        """Calcula el subtotal antes de descuento"""
        if self.total is None:
            return Decimal('0.00')
        return self.total + self.descuento

    @property
    def cantidad_productos(self):
        """Retorna la cantidad total de productos vendidos"""
        return self.detalles.aggregate(
            total=models.Sum('cantidad')
        )['total'] or 0


class SaleDetails(models.Model):
    """
    Modelo de detalle de venta.
    Representa cada producto vendido en una transacción.
    """

    venta = models.ForeignKey(
        Sales,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Venta'
    )

    producto = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='ventas_detalle',
        verbose_name='Producto'
    )

    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad',
        help_text='Cantidad de productos vendidos'
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio Unitario',
        help_text='Precio por unidad al momento de la venta'
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Subtotal',
        help_text='Total para este producto (cantidad × precio)'
    )

    descuento_aplicado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Descuento Aplicado',
        help_text='Descuento aplicado a este producto'
    )

    class Meta:
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'
        ordering = ['venta', 'id']
        indexes = [
            models.Index(fields=['venta']),
            models.Index(fields=['producto']),
        ]

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} - ${self.subtotal}"

    def save(self, *args, **kwargs):
        """
        Calcula automáticamente el subtotal y reduce el stock.
        """
        self.subtotal = (self.cantidad * self.precio_unitario) - self.descuento_aplicado

        if not self.pk and self.venta.estado == 'COMPLETADA':
            if self.producto.stock_actual < self.cantidad:
                raise ValueError(
                    f'Stock insuficiente para {self.producto.nombre}. '
                    f'Disponible: {self.producto.stock_actual}, Solicitado: {self.cantidad}'
                )
            self.producto.stock_actual -= self.cantidad
            self.producto.save()

        super().save(*args, **kwargs)
