from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from .forms import LoginForm


@sensitive_post_parameters('password')
@csrf_protect
@never_cache
def login_view(request):
    """
    Vista de login con protecciones de seguridad:
    - @sensitive_post_parameters: Oculta contraseña en logs de error
    - @csrf_protect: Protección CSRF
    - @never_cache: Previene cache del formulario
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Configurar duración de sesión según remember_me
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)

            messages.success(request, f'¡Bienvenido, {user.username}!')

            # Redirigir a la página solicitada o a home
            next_url = request.GET.get('next', '/')
            return redirect(next_url)

        else:
            messages.error(request, 'Por favor corrige los errores.')

    else:
        form = LoginForm()

    context = {
        'form': form,
        'title': 'Iniciar Sesión'
    }

    return render(request, 'accounts/login.html', context)


@login_required
def logout_view(request):
    """
    Vista de logout.
    Requiere que el usuario esté autenticado.
    """
    username = request.user.username
    logout(request)
    messages.info(request, f'Sesión cerrada. ¡Hasta pronto, {username}!')
    return redirect('login')


def home_view(request):
    """
    Vista de home.
    Muestra información del usuario si está autenticado.
    """
    context = {
        'title': 'RubiPerfumeria - Home'
    }
    return render(request, 'accounts/home.html', context)
