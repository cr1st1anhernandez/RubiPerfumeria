from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Crea perfiles faltantes para usuarios que no tienen UserProfile'

    def handle(self, *args, **options):
        users_without_profile = []
        users_fixed = 0

        # Buscar usuarios sin perfil
        for user in User.objects.all():
            if not hasattr(user, 'profile'):
                users_without_profile.append(user)

        if not users_without_profile:
            self.stdout.write(
                self.style.SUCCESS('Todos los usuarios ya tienen perfil')
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f'Encontrados {len(users_without_profile)} usuarios sin perfil'
            )
        )

        # Crear perfiles faltantes
        for user in users_without_profile:
            # Determinar el rol basado en si es superuser o staff
            if user.is_superuser:
                rol = 'ADMINISTRADOR'
            elif user.is_staff:
                rol = 'SUPERVISOR'
            else:
                rol = 'CAJERO'

            UserProfile.objects.create(user=user, rol=rol)
            users_fixed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Perfil creado para {user.username} con rol {rol}'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n¡Completado! {users_fixed} perfiles creados'
            )
        )
