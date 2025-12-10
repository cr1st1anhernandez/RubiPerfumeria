from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    """
    Formulario de login con validación de seguridad.
    Protección contra enumeración de usuarios.
    """
    username = forms.CharField(
        max_length=150,
        required=True,
        label='Usuario'
    )

    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput,
        label='Contraseña'
    )

    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label='Recordarme'
    )

    def __init__(self, *args, **kwargs):
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        """
        Validación del formulario.
        Usa mensajes genéricos para prevenir enumeración de usuarios.
        """
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            self.user = authenticate(username=username, password=password)

            if self.user is None:
                raise ValidationError(
                    'Usuario o contraseña incorrectos.',
                    code='invalid_login'
                )

            if not self.user.is_active:
                raise ValidationError(
                    'Esta cuenta está inactiva.',
                    code='inactive'
                )

        return cleaned_data

    def get_user(self):
        """Retorna el usuario autenticado."""
        return self.user
