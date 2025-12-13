#!/usr/bin/env python
"""
Script para configurar usuario como ADMINISTRADOR
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from pos.models import UserProfile

# Obtener el usuario 'admin'
try:
    user = User.objects.get(username='admin')
    print(f"✓ Usuario encontrado: {user.username}")

    # Crear o actualizar UserProfile
    profile, created = UserProfile.objects.get_or_create(user=user)

    if created:
        print("✓ UserProfile creado")
    else:
        print(f"✓ UserProfile existente (rol actual: {profile.rol})")

    # Asignar rol de ADMINISTRADOR
    profile.rol = 'ADMINISTRADOR'
    profile.save()

    print(f"✅ Usuario '{user.username}' ahora es ADMINISTRADOR")
    print(f"✅ Recarga la página para ver el Dashboard")

except User.DoesNotExist:
    print("❌ Usuario 'admin' no encontrado")
    print("Crea el usuario con: python manage.py createsuperuser")
