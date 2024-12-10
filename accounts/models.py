from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROL_CHOICES = [
        ('ADMINISTRADOR', 'Administrador'),
        ('SUPERVISOR', 'Supervisor'),
        ('CAJERO', 'Cajero'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='CAJERO')
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.username} - {self.get_rol_display()}"

    def es_administrador(self):
        return self.rol == 'ADMINISTRADOR'

    def es_supervisor(self):
        return self.rol == 'SUPERVISOR'

    def puede_gestionar_inventario(self):
        return self.rol in ['ADMINISTRADOR', 'SUPERVISOR']

    def puede_vender(self):
        return self.rol in ['ADMINISTRADOR', 'SUPERVISOR', 'CAJERO']
