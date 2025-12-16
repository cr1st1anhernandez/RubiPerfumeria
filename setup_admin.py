#!/usr/bin/env python
"""
Script de configuración rápida para Rubi Perfumeria
Este script crea un usuario administrador y arregla perfiles faltantes.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.core.management import call_command

def main():
    print("=" * 60)
    print("CONFIGURACIÓN DE RUBI PERFUMERIA")
    print("=" * 60)
    print()

    # Paso 1: Arreglar perfiles faltantes
    print("Paso 1: Verificando y arreglando perfiles de usuarios...")
    print("-" * 60)
    call_command('fix_user_profiles')
    print()

    # Paso 2: Crear/actualizar usuario admin
    print("Paso 2: Configurando usuario administrador...")
    print("-" * 60)
    call_command('setup_admin')
    print()

    print("=" * 60)
    print("¡CONFIGURACIÓN COMPLETADA!")
    print("=" * 60)

if __name__ == '__main__':
    main()
