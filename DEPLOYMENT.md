# Guía de Despliegue - Rubi Perfumeria

## Problema: Usuarios sin roles en producción

Cuando subes la base de datos a producción, los usuarios pueden no tener perfiles (y por lo tanto no tienen roles asignados). Esto impide crear productos y realizar otras operaciones.

## Solución Rápida

Después de subir tu código al servidor, ejecuta:

```bash
# Opción 1: Script automático (recomendado)
python setup_admin.py

# Opción 2: Comandos manuales
python manage.py fix_user_profiles
python manage.py setup_admin
```

## ¿Qué hace cada comando?

### `fix_user_profiles`
- Busca todos los usuarios que no tienen perfil
- Crea automáticamente perfiles para ellos
- Asigna roles basados en permisos existentes:
  - Superusers → ADMINISTRADOR
  - Staff → SUPERVISOR
  - Otros → CAJERO

### `setup_admin`
- Crea o actualiza un usuario administrador
- Por defecto: username=`admin`, password=`admin123`
- Puedes personalizarlo:

```bash
python manage.py setup_admin --username=miusuario --password=micontraseña --email=mi@email.com
```

## Proceso de Despliegue Completo

1. **En tu servidor, actualiza el código:**
   ```bash
   git pull origin prod
   ```

2. **Activa el entorno virtual:**
   ```bash
   source venv/bin/activate
   ```

3. **Instala dependencias (si hay cambios):**
   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecuta migraciones:**
   ```bash
   python manage.py migrate
   ```

5. **Arregla perfiles y crea admin:**
   ```bash
   python setup_admin.py
   ```

6. **Recolecta archivos estáticos (si usas servidor web):**
   ```bash
   python manage.py collectstatic --noinput
   ```

7. **Reinicia el servidor:**
   ```bash
   # Dependiendo de tu configuración:
   sudo systemctl restart gunicorn
   # o
   sudo systemctl restart uwsgi
   # o reinicia tu servidor web
   ```

## Verificación

Para verificar que todo está correcto:

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from accounts.models import UserProfile

# Ver todos los usuarios con sus roles
for user in User.objects.all():
    if hasattr(user, 'profile'):
        print(f"{user.username}: {user.profile.get_rol_display()}")
    else:
        print(f"{user.username}: SIN PERFIL ⚠️")
```

## Notas Importantes

- **Cambia la contraseña del admin** después del primer login
- Los perfiles se crean automáticamente para nuevos usuarios (gracias a las señales en `accounts/signals.py`)
- Si migras la base de datos, siempre ejecuta `fix_user_profiles` después

## Troubleshooting

### "No module named 'django'"
```bash
source venv/bin/activate
```

### "Table doesn't exist"
```bash
python manage.py migrate
```

### "Usuario sin permisos para crear productos"
```bash
python manage.py fix_user_profiles
# Luego verifica el rol del usuario en el admin panel
```
