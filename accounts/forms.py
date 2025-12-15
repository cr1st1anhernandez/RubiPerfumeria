from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario',
        max_length=150
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput()
    )
