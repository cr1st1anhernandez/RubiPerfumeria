from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Perfume(models.Model):
    TIPO_CHOICES = [
        ('EDT', 'Eau de Toilette'),
        ('EDP', 'Eau de Parfum'),
        ('EDC', 'Eau de Cologne'),
        ('PARFUM', 'Parfum'),
        ('SPLASH', 'Splash'),
    ]

    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('U', 'Unisex'),
    ]

    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    marca = models.CharField(max_length=100, verbose_name='Marca')
    descripcion = models.TextField(verbose_name='Descripción', blank=True)
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio'
    )
    volumen = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Volumen (ml)',
        help_text='Volumen en mililitros'
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        verbose_name='Tipo de perfume'
    )
    genero = models.CharField(
        max_length=1,
        choices=GENERO_CHOICES,
        verbose_name='Género'
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Stock disponible'
    )
    imagen = models.ImageField(
        upload_to='perfumes/',
        blank=True,
        null=True,
        verbose_name='Imagen'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

    class Meta:
        verbose_name = 'Perfume'
        verbose_name_plural = 'Perfumes'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.nombre} - {self.marca} ({self.volumen}ml)"

    @property
    def disponible(self):
        return self.activo and self.stock > 0
