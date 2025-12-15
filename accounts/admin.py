from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil'
    fields = ('rol', 'telefono', 'direccion')


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_rol', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'profile__rol')
    search_fields = ('username', 'first_name', 'last_name', 'email')

    def get_rol(self, obj):
        return obj.profile.get_rol_display() if hasattr(obj, 'profile') else 'Sin perfil'
    get_rol.short_description = 'Rol'


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
