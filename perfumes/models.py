from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.

class Perfume(models.Model):
    TIPO_CHOICES = [
        ('EDP', 'Eau de Parfum'),
        ('EDT', 'Eau de Toilette'),
        ('EDC', 'Eau de Cologne'),
        ('PARFUM', 'Parfum'),
        ('SPLASH', 'Body Splash'),
    ]

    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('U', 'Unisex'),
    ]

    # Información básica
    nombre = models.CharField(max_length=200)
    marca = models.CharField(max_length=100)
    distribuidor = models.CharField(max_length=150, blank=True, null=True, help_text="Distribuidor del producto")
    descripcion = models.TextField(blank=True, null=True)
    codigo_barras = models.CharField(max_length=50, unique=True, blank=True, null=True)

    # Clasificación
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='EDP')
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, default='U')

    # Notas olfativas
    notas_superiores = models.TextField(help_text="Notas de salida (ej: bergamota, limón)")
    notas_medias = models.TextField(help_text="Notas de corazón (ej: jazmín, rosa)")
    notas_base = models.TextField(help_text="Notas de fondo (ej: almizcle, vainilla)")

    # Características técnicas
    volumen = models.IntegerField(validators=[MinValueValidator(1)], help_text="Volumen en ml")
    concentracion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Concentración de esencia en %",
        blank=True,
        null=True
    )
    anio_lanzamiento = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        blank=True,
        null=True
    )

    # Inventario y precio
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.IntegerField(validators=[MinValueValidator(0)], default=0)

    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['marca', 'nombre']
        verbose_name = 'Perfume'
        verbose_name_plural = 'Perfumes'

    def __str__(self):
        return f"{self.marca} - {self.nombre} ({self.volumen}ml)"

    def esta_en_stock(self):
        return self.stock > 0
