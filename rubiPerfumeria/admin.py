from django.contrib import admin
from .models import Perfume

@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'marca', 'tipo', 'genero', 'volumen', 'precio', 'stock', 'activo', 'fecha_creacion']
    list_filter = ['tipo', 'genero', 'activo', 'marca']
    search_fields = ['nombre', 'marca', 'descripcion']
    list_editable = ['stock', 'activo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'marca', 'descripcion', 'imagen')
        }),
        ('Características', {
            'fields': ('tipo', 'genero', 'volumen', 'precio')
        }),
        ('Inventario', {
            'fields': ('stock', 'activo')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
