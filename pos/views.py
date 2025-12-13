from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F, Avg, Max, Min
from django.db.models.functions import TruncDate, TruncHour, Coalesce
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from datetime import timedelta, datetime
from .models import Product, Sales, SaleDetails, Inventory, UserProfile
from .forms import (
    ProductSearchForm, AddToCartForm, CompleteSaleForm,
    InventoryMovementForm, ProductFilterForm
)


@login_required
def pos_index(request):
    """Vista principal del POS - Caja registradora"""
    search_form = ProductSearchForm()
    cart = request.session.get('cart', {})

    # Calcular totales del carrito
    cart_items = []
    subtotal = Decimal('0.00')

    for product_id, item in cart.items():
        try:
            product = Product.objects.get(id=product_id)
            item_total = product.precio * item['cantidad']
            cart_items.append({
                'product': product,
                'cantidad': item['cantidad'],
                'subtotal': item_total
            })
            subtotal += item_total
        except Product.DoesNotExist:
            continue

    context = {
        'search_form': search_form,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'cart_count': sum(item['cantidad'] for item in cart.values())
    }

    return render(request, 'pos/index.html', context)


@login_required
def search_product(request):
    """Buscar productos para agregar al carrito"""
    search_form = ProductSearchForm(request.GET)
    products = []

    if search_form.is_valid():
        search_query = search_form.cleaned_data.get('search')
        if search_query:
            products = Product.objects.filter(
                Q(codigo_barras__icontains=search_query) |
                Q(nombre__icontains=search_query) |
                Q(marca__icontains=search_query),
                activo=True
            )[:10]  # Limitar a 10 resultados

    return render(request, 'pos/search_results.html', {
        'products': products,
        'search_query': search_form.cleaned_data.get('search', '')
    })


@login_required
def add_to_cart(request, product_id):
    """Agregar producto al carrito"""
    product = get_object_or_404(Product, id=product_id, activo=True)

    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 1))

        # Verificar stock disponible
        if product.stock_actual < cantidad:
            messages.error(
                request,
                f'Stock insuficiente. Disponible: {product.stock_actual}'
            )
            return redirect('pos:index')

        # Obtener o crear carrito en sesión
        cart = request.session.get('cart', {})

        # Agregar o actualizar producto en carrito
        if str(product_id) in cart:
            nueva_cantidad = cart[str(product_id)]['cantidad'] + cantidad
            if product.stock_actual < nueva_cantidad:
                messages.error(
                    request,
                    f'Stock insuficiente. Disponible: {product.stock_actual}'
                )
                return redirect('pos:index')
            cart[str(product_id)]['cantidad'] = nueva_cantidad
        else:
            cart[str(product_id)] = {
                'cantidad': cantidad,
                'precio': str(product.precio)
            }

        request.session['cart'] = cart
        request.session.modified = True

        messages.success(
            request,
            f'"{product.nombre}" agregado al carrito'
        )

    return redirect('pos:index')


@login_required
def remove_from_cart(request, product_id):
    """Eliminar producto del carrito"""
    cart = request.session.get('cart', {})

    if str(product_id) in cart:
        product = get_object_or_404(Product, id=product_id)
        del cart[str(product_id)]
        request.session['cart'] = cart
        request.session.modified = True
        messages.success(request, f'"{product.nombre}" eliminado del carrito')

    return redirect('pos:index')


@login_required
def update_cart_quantity(request, product_id):
    """Actualizar cantidad de producto en carrito"""
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 1))
        cart = request.session.get('cart', {})

        if str(product_id) in cart:
            product = get_object_or_404(Product, id=product_id)

            if product.stock_actual < cantidad:
                messages.error(
                    request,
                    f'Stock insuficiente. Disponible: {product.stock_actual}'
                )
            else:
                cart[str(product_id)]['cantidad'] = cantidad
                request.session['cart'] = cart
                request.session.modified = True
                messages.success(request, 'Cantidad actualizada')

    return redirect('pos:index')


@login_required
def checkout(request):
    """Vista de checkout para completar la venta"""
    cart = request.session.get('cart', {})

    if not cart:
        messages.warning(request, 'El carrito está vacío')
        return redirect('pos:index')

    # Calcular totales
    cart_items = []
    subtotal = Decimal('0.00')

    for product_id, item in cart.items():
        try:
            product = Product.objects.get(id=product_id)
            item_total = product.precio * item['cantidad']
            cart_items.append({
                'product': product,
                'cantidad': item['cantidad'],
                'precio_unitario': product.precio,
                'subtotal': item_total
            })
            subtotal += item_total
        except Product.DoesNotExist:
            continue

    if request.method == 'POST':
        form = CompleteSaleForm(request.POST)
        if form.is_valid():
            # Crear la venta
            descuento = form.cleaned_data.get('descuento') or Decimal('0.00')
            total = subtotal - descuento

            venta = Sales.objects.create(
                total=total,
                metodo_pago=form.cleaned_data['metodo_pago'],
                cajero=request.user,
                descuento=descuento,
                notas=form.cleaned_data.get('notas', '')
            )

            # Crear detalles de venta
            for item in cart_items:
                SaleDetails.objects.create(
                    venta=venta,
                    producto=item['product'],
                    cantidad=item['cantidad'],
                    precio_unitario=item['precio_unitario']
                )

            # Limpiar carrito
            request.session['cart'] = {}
            request.session.modified = True

            messages.success(
                request,
                f'Venta completada. Ticket: {venta.numero_ticket}'
            )
            return redirect('pos:sale_detail', pk=venta.pk)
    else:
        form = CompleteSaleForm()

    context = {
        'form': form,
        'cart_items': cart_items,
        'subtotal': subtotal
    }

    return render(request, 'pos/checkout.html', context)


@login_required
def clear_cart(request):
    """Vaciar el carrito"""
    request.session['cart'] = {}
    request.session.modified = True
    messages.success(request, 'Carrito vaciado')
    return redirect('pos:index')


@login_required
def product_list(request):
    """Lista de productos con filtros"""
    filter_form = ProductFilterForm(request.GET)
    products = Product.objects.all()

    if filter_form.is_valid():
        categoria = filter_form.cleaned_data.get('categoria')
        genero = filter_form.cleaned_data.get('genero')
        solo_disponibles = filter_form.cleaned_data.get('solo_disponibles')
        bajo_stock = filter_form.cleaned_data.get('bajo_stock')

        if categoria:
            products = products.filter(categoria=categoria)

        if genero:
            products = products.filter(genero=genero)

        if solo_disponibles:
            products = products.filter(activo=True, stock_actual__gt=0)

        if bajo_stock:
            from django.db.models import F
            products = products.filter(stock_actual__lte=F('stock_minimo'))

    context = {
        'products': products,
        'filter_form': filter_form
    }

    return render(request, 'pos/product_list.html', context)


@login_required
def sale_list(request):
    """Lista de ventas realizadas"""
    sales = Sales.objects.all().select_related('cajero').order_by('-fecha_hora')

    # Filtrar por fecha si se proporciona
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    if fecha_desde:
        sales = sales.filter(fecha_hora__date__gte=fecha_desde)

    if fecha_hasta:
        sales = sales.filter(fecha_hora__date__lte=fecha_hasta)

    context = {
        'sales': sales
    }

    return render(request, 'pos/sale_list.html', context)


@login_required
def sale_detail(request, pk):
    """Detalle de una venta específica"""
    sale = get_object_or_404(Sales, pk=pk)
    details = sale.detalles.all().select_related('producto')

    context = {
        'sale': sale,
        'details': details
    }

    return render(request, 'pos/sale_detail.html', context)


@login_required
def inventory_movement(request):
    """Registrar movimiento de inventario"""
    if request.method == 'POST':
        form = InventoryMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.usuario = request.user
            movement.save()

            messages.success(
                request,
                f'Movimiento de inventario registrado para {movement.producto.nombre}'
            )
            return redirect('pos:product_list')
    else:
        form = InventoryMovementForm()

    context = {
        'form': form
    }

    return render(request, 'pos/inventory_movement.html', context)


# ============================================================================
# DASHBOARD DE ADMINISTRADOR
# ============================================================================

def require_admin_or_supervisor(view_func):
    """Decorador para requerir rol de ADMINISTRADOR o SUPERVISOR"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.rol not in ['ADMINISTRADOR', 'SUPERVISOR']:
                messages.error(request, 'No tienes permisos para acceder al dashboard')
                return redirect('pos:index')
        except UserProfile.DoesNotExist:
            messages.error(request, 'Usuario sin perfil asignado')
            return redirect('pos:index')

        return view_func(request, *args, **kwargs)
    return wrapper


@require_admin_or_supervisor
def dashboard_view(request):
    """Vista principal del dashboard de administrador"""
    return render(request, 'pos/dashboard/index.html')


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_kpis(request):
    """API: KPIs principales del dashboard"""
    # Obtener rango de fechas (por defecto: hoy)
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde', today)
    fecha_hasta = request.GET.get('fecha_hasta', today)

    # Convertir a datetime si es necesario
    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    # Ventas del período actual
    ventas_actuales = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).aggregate(
        total=Coalesce(Sum('total'), Decimal('0.00')),
        cantidad=Count('id')
    )

    # Calcular período anterior (mismo número de días)
    dias_periodo = (fecha_hasta - fecha_desde).days + 1
    fecha_desde_anterior = fecha_desde - timedelta(days=dias_periodo)
    fecha_hasta_anterior = fecha_desde - timedelta(days=1)

    # Ventas del período anterior
    ventas_anteriores = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde_anterior,
        fecha_hora__date__lte=fecha_hasta_anterior,
        estado='COMPLETADA'
    ).aggregate(
        total=Coalesce(Sum('total'), Decimal('0.00'))
    )

    # Calcular porcentaje de cambio
    if ventas_anteriores['total'] > 0:
        cambio_porcentual = float(
            ((ventas_actuales['total'] - ventas_anteriores['total']) /
             ventas_anteriores['total']) * 100
        )
    else:
        cambio_porcentual = 100.0 if ventas_actuales['total'] > 0 else 0.0

    # Productos con bajo stock
    productos_bajo_stock = Product.objects.filter(
        stock_actual__lte=F('stock_minimo'),
        activo=True
    ).count()

    # Mejor cajero del período
    mejor_cajero = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).values(
        'cajero__username',
        'cajero__first_name',
        'cajero__last_name'
    ).annotate(
        total_ventas=Sum('total')
    ).order_by('-total_ventas').first()

    # Promedio de venta
    promedio_venta = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).aggregate(
        promedio=Coalesce(Avg('total'), Decimal('0.00'))
    )

    return JsonResponse({
        'ventas_total': float(ventas_actuales['total']),
        'ventas_cantidad': ventas_actuales['cantidad'],
        'ventas_cambio_porcentual': round(cambio_porcentual, 2),
        'productos_bajo_stock': productos_bajo_stock,
        'mejor_cajero': {
            'nombre': f"{mejor_cajero.get('cajero__first_name', '')} {mejor_cajero.get('cajero__last_name', '')}".strip() or mejor_cajero.get('cajero__username', 'N/A') if mejor_cajero else 'N/A',
            'total': float(mejor_cajero.get('total_ventas', 0)) if mejor_cajero else 0
        },
        'promedio_venta': float(promedio_venta['promedio']),
        'periodo': {
            'desde': str(fecha_desde),
            'hasta': str(fecha_hasta)
        }
    })


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_sales_trend(request):
    """API: Tendencia de ventas por día"""
    # Obtener rango de fechas (por defecto: últimos 7 días)
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta', today)

    if not fecha_desde:
        fecha_desde = today - timedelta(days=6)  # Últimos 7 días

    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    # Ventas agrupadas por día
    ventas_por_dia = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).annotate(
        dia=TruncDate('fecha_hora')
    ).values('dia').annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('dia')

    # Formatear respuesta
    data = {
        'labels': [item['dia'].strftime('%Y-%m-%d') for item in ventas_por_dia],
        'ventas': [float(item['total']) for item in ventas_por_dia],
        'cantidad': [item['cantidad'] for item in ventas_por_dia]
    }

    return JsonResponse(data)


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_sales_by_cashier(request):
    """API: Ventas por cajero"""
    # Obtener rango de fechas
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde', today)
    fecha_hasta = request.GET.get('fecha_hasta', today)

    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    # Ventas por cajero
    ventas_por_cajero = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).values(
        'cajero__username',
        'cajero__first_name',
        'cajero__last_name'
    ).annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('-total')[:10]  # Top 10 cajeros

    # Formatear respuesta
    data = {
        'labels': [
            f"{item.get('cajero__first_name', '')} {item.get('cajero__last_name', '')}".strip() or item.get('cajero__username', 'N/A')
            for item in ventas_por_cajero
        ],
        'ventas': [float(item['total']) for item in ventas_por_cajero],
        'cantidad': [item['cantidad'] for item in ventas_por_cajero]
    }

    return JsonResponse(data)


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_payment_methods(request):
    """API: Distribución de métodos de pago"""
    # Obtener rango de fechas
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde', today)
    fecha_hasta = request.GET.get('fecha_hasta', today)

    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    # Ventas por método de pago
    ventas_por_metodo = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).values('metodo_pago').annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('-total')

    # Mapeo de métodos de pago
    metodos_map = {
        'EFECTIVO': 'Efectivo',
        'TARJETA': 'Tarjeta',
        'TRANSFERENCIA': 'Transferencia',
        'OTRO': 'Otro'
    }

    # Formatear respuesta
    data = {
        'labels': [metodos_map.get(item['metodo_pago'], item['metodo_pago']) for item in ventas_por_metodo],
        'ventas': [float(item['total']) for item in ventas_por_metodo],
        'cantidad': [item['cantidad'] for item in ventas_por_metodo]
    }

    return JsonResponse(data)


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_top_products(request):
    """API: Top productos más vendidos"""
    # Obtener rango de fechas
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde', today)
    fecha_hasta = request.GET.get('fecha_hasta', today)

    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    limit = int(request.GET.get('limit', 10))

    # Top productos vendidos
    top_productos = SaleDetails.objects.filter(
        venta__fecha_hora__date__gte=fecha_desde,
        venta__fecha_hora__date__lte=fecha_hasta,
        venta__estado='COMPLETADA'
    ).values(
        'producto__nombre',
        'producto__marca'
    ).annotate(
        cantidad_vendida=Sum('cantidad'),
        ingresos=Sum(F('cantidad') * F('precio_unitario'))
    ).order_by('-cantidad_vendida')[:limit]

    # Formatear respuesta
    data = {
        'labels': [
            f"{item['producto__marca']} {item['producto__nombre']}" if item['producto__marca']
            else item['producto__nombre']
            for item in top_productos
        ],
        'cantidad': [item['cantidad_vendida'] for item in top_productos],
        'ingresos': [float(item['ingresos']) for item in top_productos]
    }

    return JsonResponse(data)


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_sales_by_category(request):
    """API: Ventas por categoría"""
    # Obtener rango de fechas
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde', today)
    fecha_hasta = request.GET.get('fecha_hasta', today)

    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    # Ventas por categoría
    ventas_por_categoria = SaleDetails.objects.filter(
        venta__fecha_hora__date__gte=fecha_desde,
        venta__fecha_hora__date__lte=fecha_hasta,
        venta__estado='COMPLETADA'
    ).values(
        'producto__categoria'
    ).annotate(
        total=Sum(F('cantidad') * F('precio_unitario')),
        cantidad=Sum('cantidad')
    ).order_by('-total')

    # Mapeo de categorías
    categorias_map = {
        'EDT': 'Eau de Toilette',
        'EDP': 'Eau de Parfum',
        'EDC': 'Eau de Cologne',
        'PARFUM': 'Parfum',
        'SPLASH': 'Splash',
        'ACCESORIO': 'Accesorio',
        'OTRO': 'Otro'
    }

    # Formatear respuesta
    data = {
        'labels': [
            categorias_map.get(item['producto__categoria'], item['producto__categoria'])
            for item in ventas_por_categoria
        ],
        'ventas': [float(item['total']) for item in ventas_por_categoria],
        'cantidad': [item['cantidad'] for item in ventas_por_categoria]
    }

    return JsonResponse(data)


@require_admin_or_supervisor
@require_http_methods(["GET"])
def dashboard_api_sales_by_hour(request):
    """API: Ventas por hora del día"""
    # Obtener rango de fechas
    today = timezone.now().date()
    fecha_desde = request.GET.get('fecha_desde', today)
    fecha_hasta = request.GET.get('fecha_hasta', today)

    if isinstance(fecha_desde, str):
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
    if isinstance(fecha_hasta, str):
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()

    # Ventas por hora
    ventas_por_hora = Sales.objects.filter(
        fecha_hora__date__gte=fecha_desde,
        fecha_hora__date__lte=fecha_hasta,
        estado='COMPLETADA'
    ).annotate(
        hora=TruncHour('fecha_hora')
    ).values('hora').annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('hora')

    # Formatear respuesta
    data = {
        'labels': [item['hora'].strftime('%H:00') for item in ventas_por_hora],
        'ventas': [float(item['total']) for item in ventas_por_hora],
        'cantidad': [item['cantidad'] for item in ventas_por_hora]
    }

    return JsonResponse(data)
