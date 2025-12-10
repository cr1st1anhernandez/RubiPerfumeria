from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def role_required(*roles):
    """
    Decorator to check if user has one of the required roles.
    Usage: @role_required('ADMINISTRADOR', 'SUPERVISOR')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not hasattr(request.user, 'profile'):
                messages.error(request, 'Tu usuario no tiene un perfil asignado. Contacta al administrador.')
                return redirect('home')

            if request.user.profile.rol in roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'No tienes permisos para acceder a esta página.')
                return redirect('home')

        return wrapper
    return decorator


def administrador_required(view_func):
    """Decorator to check if user is an administrator."""
    return role_required('ADMINISTRADOR')(view_func)


def supervisor_required(view_func):
    """Decorator to check if user is a supervisor or administrator."""
    return role_required('ADMINISTRADOR', 'SUPERVISOR')(view_func)


def cajero_required(view_func):
    """Decorator to check if user is a cajero, supervisor, or administrator."""
    return role_required('ADMINISTRADOR', 'SUPERVISOR', 'CAJERO')(view_func)
