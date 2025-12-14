from django.contrib import admin
from .models import Perfume

# Register your models here.

@admin.register(Perfume)
class PerfumeAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'marca', 'tipo', 'genero', 'volumen', 'precio', 'stock', 'esta_en_stock']
    list_filter = ['tipo', 'genero', 'marca']
    search_fields = ['nombre', 'marca', 'codigo_barras']
    ordering = ['marca', 'nombre']
