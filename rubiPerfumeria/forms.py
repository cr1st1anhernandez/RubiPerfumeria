from django import forms
from .models import Perfume

class PerfumeForm(forms.ModelForm):
    class Meta:
        model = Perfume
        fields = ['nombre', 'marca', 'descripcion', 'precio', 'volumen', 'tipo', 'genero', 'stock', 'imagen', 'activo']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }
