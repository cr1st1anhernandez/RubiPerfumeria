from django import forms
from decimal import Decimal


class ProcesarPagoForm(forms.Form):
    """Formulario para procesar el pago de una venta"""
    monto_recibido = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        label='Monto Recibido',
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'placeholder': '0.00',
            'class': 'form-control'
        })
    )
    descuento_general = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        initial=Decimal('0'),
        required=False,
        label='Descuento General (%)',
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'placeholder': '0.00',
            'class': 'form-control'
        })
    )
    notas = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Observaciones (opcional)',
            'class': 'form-control'
        })
    )


class DevolucionForm(forms.Form):
    """Formulario para confirmar devolución"""
    confirmar = forms.CharField(
        widget=forms.HiddenInput(),
        initial='SI'
    )
    motivo = forms.CharField(
        required=True,
        label='Motivo de la devolución',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Describe el motivo de la devolución',
            'class': 'form-control'
        })
    )
