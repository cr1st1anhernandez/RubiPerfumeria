from django import forms
from .models import Product, Sales, SaleDetails, Inventory


class ProductSearchForm(forms.Form):
    """Formulario para buscar productos por código de barras o nombre"""
    search = forms.CharField(
        max_length=200,
        required=False,
        label='Buscar producto',
        widget=forms.TextInput(attrs={
            'placeholder': 'Código de barras o nombre del producto'
        })
    )


class AddToCartForm(forms.Form):
    """Formulario para agregar productos al carrito"""
    product_id = forms.IntegerField(widget=forms.HiddenInput())
    cantidad = forms.IntegerField(
        min_value=1,
        initial=1,
        label='Cantidad'
    )


class CompleteSaleForm(forms.Form):
    """Formulario para completar una venta"""
    METODO_PAGO_CHOICES = [
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('MIXTO', 'Mixto'),
    ]

    metodo_pago = forms.ChoiceField(
        choices=METODO_PAGO_CHOICES,
        label='Método de Pago',
        widget=forms.RadioSelect
    )
    descuento = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0.00,
        min_value=0,
        required=False,
        label='Descuento'
    )
    notas = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='Notas'
    )


class InventoryMovementForm(forms.ModelForm):
    """Formulario para registrar movimientos de inventario"""
    class Meta:
        model = Inventory
        fields = ['producto', 'cantidad', 'tipo', 'motivo']
        widgets = {
            'motivo': forms.Textarea(attrs={'rows': 3}),
        }


class ProductFilterForm(forms.Form):
    """Formulario para filtrar productos"""
    categoria = forms.ChoiceField(
        choices=[('', 'Todas')] + list(Product.CATEGORIA_CHOICES),
        required=False,
        label='Categoría'
    )
    genero = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Product.GENERO_CHOICES),
        required=False,
        label='Género'
    )
    solo_disponibles = forms.BooleanField(
        required=False,
        initial=True,
        label='Solo productos disponibles'
    )
    bajo_stock = forms.BooleanField(
        required=False,
        initial=False,
        label='Solo productos con bajo stock'
    )


class SalesReportFilterForm(forms.Form):
    """Formulario para filtrar el reporte de ventas"""
    fecha_desde = forms.DateField(
        required=False,
        label='Desde',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    fecha_hasta = forms.DateField(
        required=False,
        label='Hasta',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    cajero = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label='Cajero',
        empty_label='Todos'
    )
    metodo_pago = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Sales.METODO_PAGO_CHOICES),
        required=False,
        label='Método de Pago'
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Sales.ESTADO_CHOICES),
        required=False,
        label='Estado'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['cajero'].queryset = User.objects.filter(
            ventas_realizadas__isnull=False
        ).distinct()


class InventoryReportFilterForm(forms.Form):
    """Formulario para filtrar el reporte de inventario"""
    categoria = forms.ChoiceField(
        choices=[('', 'Todas')] + list(Product.CATEGORIA_CHOICES),
        required=False,
        label='Categoría'
    )
    genero = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Product.GENERO_CHOICES),
        required=False,
        label='Género'
    )
    marca = forms.CharField(
        max_length=100,
        required=False,
        label='Marca'
    )
    solo_bajo_stock = forms.BooleanField(
        required=False,
        initial=False,
        label='Solo productos con bajo stock'
    )
    solo_activos = forms.BooleanField(
        required=False,
        initial=True,
        label='Solo productos activos'
    )
