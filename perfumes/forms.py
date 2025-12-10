from django import forms
from .models import Perfume


class PerfumeForm(forms.ModelForm):
    class Meta:
        model = Perfume
        fields = [
            'nombre',
            'marca',
            'descripcion',
            'codigo_barras',
            'tipo',
            'genero',
            'notas_superiores',
            'notas_medias',
            'notas_base',
            'volumen',
            'concentracion',
            'anio_lanzamiento',
            'precio',
            'stock',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'notas_superiores': forms.Textarea(attrs={'rows': 2}),
            'notas_medias': forms.Textarea(attrs={'rows': 2}),
            'notas_base': forms.Textarea(attrs={'rows': 2}),
        }
