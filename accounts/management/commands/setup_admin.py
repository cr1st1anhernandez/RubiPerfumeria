from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Crea o actualiza un usuario administrador con su perfil'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Nombre de usuario (default: admin)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Contraseña (default: admin123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@rubiperfumeria.com',
            help='Email del administrador'
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']

        # Crear o obtener el usuario
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Usuario "{username}" creado exitosamente')
            )
        else:
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.WARNING(f'Usuario "{username}" ya existía, actualizado')
            )

        # Crear o actualizar el perfil
        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'rol': 'ADMINISTRADOR'}
        )

        if not profile_created and profile.rol != 'ADMINISTRADOR':
            profile.rol = 'ADMINISTRADOR'
            profile.save()
            self.stdout.write(
                self.style.SUCCESS(f'Perfil actualizado a ADMINISTRADOR')
            )
        elif profile_created:
            self.stdout.write(
                self.style.SUCCESS(f'Perfil ADMINISTRADOR creado')
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n¡Listo! Puedes iniciar sesión con:\n'
                f'Username: {username}\n'
                f'Password: {password}'
            )
        )
