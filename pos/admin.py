from django.contrib import admin
from .models import Venta, DetalleVenta, MovimientoInventario, VentaTemporal


class DetalleVentaInline(admin.TabularInline):
    """Inline para mostrar detalles de venta en el admin de Venta"""
    model = DetalleVenta
    extra = 0
    readonly_fields = ['nombre_producto', 'precio_unitario', 'cantidad', 'descuento_porcentaje', 'descuento_monto', 'subtotal']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ['numero_ticket', 'cajero', 'total', 'estado', 'metodo_pago', 'fecha_creacion']
    list_filter = ['estado', 'metodo_pago', 'fecha_creacion', 'cajero']
    search_fields = ['numero_ticket', 'cajero__username', 'cajero__first_name', 'cajero__last_name']
    readonly_fields = ['numero_ticket', 'subtotal', 'total', 'cambio', 'fecha_creacion', 'fecha_actualizacion']
    inlines = [DetalleVentaInline]
    date_hierarchy = 'fecha_creacion'

    fieldsets = (
        ('Información Básica', {
            'fields': ('numero_ticket', 'cajero', 'estado', 'fecha_creacion', 'fecha_actualizacion')
        }),
        ('Montos', {
            'fields': ('subtotal', 'descuento_porcentaje', 'descuento_monto', 'total')
        }),
        ('Pago', {
            'fields': ('metodo_pago', 'monto_recibido', 'cambio')
        }),
        ('Notas', {
            'fields': ('notas',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # No permitir crear ventas desde el admin (solo desde el POS)
        return False

    def has_delete_permission(self, request, obj=None):
        # Solo administradores pueden eliminar ventas
        return request.user.is_superuser


@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    list_display = ['venta', 'perfume', 'cantidad', 'precio_unitario', 'subtotal']
    list_filter = ['venta__fecha_creacion']
    search_fields = ['venta__numero_ticket', 'perfume__nombre', 'nombre_producto']
    readonly_fields = ['nombre_producto', 'precio_unitario', 'subtotal', 'descuento_monto']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ['perfume', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_nuevo', 'usuario', 'fecha_creacion']
    list_filter = ['tipo_movimiento', 'fecha_creacion', 'usuario']
    search_fields = ['perfume__nombre', 'perfume__marca', 'usuario__username', 'venta__numero_ticket']
    readonly_fields = ['perfume', 'venta', 'usuario', 'tipo_movimiento', 'cantidad', 'stock_anterior', 'stock_nuevo', 'fecha_creacion']
    date_hierarchy = 'fecha_creacion'

    fieldsets = (
        ('Información del Movimiento', {
            'fields': ('perfume', 'tipo_movimiento', 'cantidad', 'usuario', 'fecha_creacion')
        }),
        ('Stock', {
            'fields': ('stock_anterior', 'stock_nuevo')
        }),
        ('Relacionado', {
            'fields': ('venta',),
            'classes': ('collapse',)
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Los movimientos se crean automáticamente, no manualmente
        return False

    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar movimientos (historial)
        return False


@admin.register(VentaTemporal)
class VentaTemporalAdmin(admin.ModelAdmin):
    list_display = ['cajero', 'perfume', 'cantidad', 'precio_unitario', 'descuento_porcentaje', 'fecha_agregado']
    list_filter = ['cajero', 'fecha_agregado']
    search_fields = ['cajero__username', 'perfume__nombre']
    readonly_fields = ['fecha_agregado']

    def has_add_permission(self, request):
        # Las ventas temporales se crean desde el POS
        return False
