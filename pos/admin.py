from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from decimal import Decimal
from .models import Product, UserProfile, Inventory, Sales, SaleDetails


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'codigo_barras',
        'nombre',
        'marca',
        'categoria',
        'precio',
        'stock_actual',
        'stock_minimo',
        'estado_stock',
        'activo',
        'fecha_creacion'
    ]

    list_filter = [
        'categoria',
        'activo',
        'marca',
        'genero',
        ('fecha_creacion', admin.DateFieldListFilter),
    ]

    search_fields = [
        'codigo_barras',
        'nombre',
        'marca',
        'descripcion'
    ]

    list_editable = [
        'precio',
        'stock_minimo',
        'activo'
    ]

    readonly_fields = [
        'fecha_creacion',
        'fecha_actualizacion',
        'disponible',
        'requiere_reabastecimiento',
        'valor_inventario',
        'imagen_preview'
    ]

    fieldsets = (
        ('Identificación', {
            'fields': (
                'codigo_barras',
                'nombre',
                'marca',
                'categoria'
            )
        }),
        ('Información del Producto', {
            'fields': (
                'descripcion',
                'volumen',
                'genero',
                'imagen',
                'imagen_preview'
            )
        }),
        ('Precio e Inventario', {
            'fields': (
                'precio',
                'stock_actual',
                'stock_minimo',
                'disponible',
                'requiere_reabastecimiento',
                'valor_inventario'
            )
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
        ('Información de Sistema', {
            'fields': (
                'fecha_creacion',
                'fecha_actualizacion'
            ),
            'classes': ('collapse',)
        }),
    )

    def estado_stock(self, obj):
        """Muestra el estado del stock con colores"""
        if obj.stock_actual <= 0:
            color = 'red'
            estado = 'SIN STOCK'
        elif obj.requiere_reabastecimiento:
            color = 'orange'
            estado = 'BAJO'
        else:
            color = 'green'
            estado = 'OK'

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            estado
        )
    estado_stock.short_description = 'Estado Stock'

    def imagen_preview(self, obj):
        """Muestra preview de la imagen"""
        if obj.imagen:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.imagen.url
            )
        return "Sin imagen"
    imagen_preview.short_description = 'Preview'

    actions = ['activar_productos', 'desactivar_productos']

    def activar_productos(self, request, queryset):
        updated = queryset.update(activo=True)
        self.message_user(request, f'{updated} productos activados.')
    activar_productos.short_description = 'Activar productos seleccionados'

    def desactivar_productos(self, request, queryset):
        updated = queryset.update(activo=False)
        self.message_user(request, f'{updated} productos desactivados.')
    desactivar_productos.short_description = 'Desactivar productos seleccionados'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'nombre_completo_display',
        'rol',
        'turno',
        'activo',
        'fecha_creacion'
    ]

    list_filter = [
        'rol',
        'turno',
        'activo',
        ('fecha_creacion', admin.DateFieldListFilter),
    ]

    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email'
    ]

    list_editable = ['rol', 'turno', 'activo']

    readonly_fields = [
        'fecha_creacion',
        'fecha_actualizacion',
        'nombre_completo_display'
    ]

    fieldsets = (
        ('Usuario', {
            'fields': ('user', 'nombre_completo_display')
        }),
        ('Información POS', {
            'fields': ('rol', 'turno', 'activo')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )

    def nombre_completo_display(self, obj):
        return obj.nombre_completo
    nombre_completo_display.short_description = 'Nombre Completo'


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = [
        'fecha',
        'producto',
        'tipo',
        'cantidad',
        'stock_anterior',
        'stock_nuevo',
        'usuario',
    ]

    list_filter = [
        'tipo',
        ('fecha', admin.DateFieldListFilter),
        'usuario',
    ]

    search_fields = [
        'producto__nombre',
        'producto__codigo_barras',
        'motivo',
        'usuario__username'
    ]

    readonly_fields = [
        'fecha',
        'stock_anterior',
        'stock_nuevo'
    ]

    fieldsets = (
        ('Movimiento', {
            'fields': (
                'producto',
                'tipo',
                'cantidad',
                'motivo'
            )
        }),
        ('Stock', {
            'fields': (
                'stock_anterior',
                'stock_nuevo'
            )
        }),
        ('Información', {
            'fields': ('usuario', 'fecha')
        }),
    )

    def save_model(self, request, obj, form, change):
        """Asigna automáticamente el usuario actual"""
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        """Prevenir eliminación de movimientos de inventario"""
        return False


class SaleDetailsInline(admin.TabularInline):
    model = SaleDetails
    extra = 1

    fields = [
        'producto',
        'cantidad',
        'precio_unitario',
        'descuento_aplicado',
        'subtotal'
    ]

    readonly_fields = ['subtotal']

    autocomplete_fields = ['producto']


@admin.register(Sales)
class SalesAdmin(admin.ModelAdmin):
    list_display = [
        'numero_ticket',
        'fecha_hora',
        'cajero',
        'total',
        'metodo_pago',
        'estado',
        'cantidad_productos_display'
    ]

    list_filter = [
        'estado',
        'metodo_pago',
        ('fecha_hora', admin.DateFieldListFilter),
        'cajero',
    ]

    search_fields = [
        'numero_ticket',
        'cajero__username',
        'notas'
    ]

    readonly_fields = [
        'numero_ticket',
        'fecha_hora',
        'subtotal_display',
        'cantidad_productos_display',
        'fecha_cancelacion'
    ]

    fieldsets = (
        ('Información de Venta', {
            'fields': (
                'numero_ticket',
                'fecha_hora',
                'cajero',
                'estado'
            )
        }),
        ('Montos', {
            'fields': (
                'subtotal_display',
                'descuento',
                'total',
                'metodo_pago'
            )
        }),
        ('Detalles Adicionales', {
            'fields': (
                'cantidad_productos_display',
                'notas'
            )
        }),
        ('Cancelación', {
            'fields': (
                'fecha_cancelacion',
                'motivo_cancelacion'
            ),
            'classes': ('collapse',)
        }),
    )

    inlines = [SaleDetailsInline]

    def cantidad_productos_display(self, obj):
        return obj.cantidad_productos
    cantidad_productos_display.short_description = 'Cant. Productos'

    def subtotal_display(self, obj):
        return obj.subtotal
    subtotal_display.short_description = 'Subtotal'

    def save_model(self, request, obj, form, change):
        """Asigna automáticamente el cajero actual si no está definido"""
        if not obj.pk and not obj.cajero_id:
            obj.cajero = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Calcula el total automáticamente basado en los detalles"""
        instances = formset.save(commit=False)

        for instance in instances:
            if not instance.precio_unitario:
                instance.precio_unitario = instance.producto.precio
            instance.save()

        formset.save_m2m()

        sale = form.instance
        total_detalles = sale.detalles.aggregate(
            total=Sum('subtotal')
        )['total'] or Decimal('0.00')

        sale.total = total_detalles - sale.descuento
        sale.save()

    actions = ['cancelar_ventas']

    def cancelar_ventas(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(estado='COMPLETADA').update(
            estado='CANCELADA',
            fecha_cancelacion=timezone.now(),
            motivo_cancelacion='Cancelada desde admin por ' + request.user.username
        )
        self.message_user(request, f'{updated} ventas canceladas.')
    cancelar_ventas.short_description = 'Cancelar ventas seleccionadas'


@admin.register(SaleDetails)
class SaleDetailsAdmin(admin.ModelAdmin):
    list_display = [
        'venta',
        'producto',
        'cantidad',
        'precio_unitario',
        'descuento_aplicado',
        'subtotal'
    ]

    list_filter = [
        ('venta__fecha_hora', admin.DateFieldListFilter),
    ]

    search_fields = [
        'venta__numero_ticket',
        'producto__nombre',
        'producto__codigo_barras'
    ]

    readonly_fields = ['subtotal']

    autocomplete_fields = ['producto', 'venta']
