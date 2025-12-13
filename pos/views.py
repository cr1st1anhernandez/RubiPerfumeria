from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from decimal import Decimal
from .models import Product, Sales, SaleDetails, Inventory
from .forms import (
    ProductSearchForm, AddToCartForm, CompleteSaleForm,
    InventoryMovementForm, ProductFilterForm, SalesReportFilterForm,
    InventoryReportFilterForm
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


@login_required
def sales_report_view(request):
    """Vista para el reporte de ventas con filtros y exportación"""
    from .reports import generate_sales_pdf, generate_sales_excel

    form = SalesReportFilterForm(request.GET or None)
    sales = Sales.objects.all().select_related('cajero').order_by('-fecha_hora')

    # Aplicar filtros
    if form.is_valid():
        fecha_desde = form.cleaned_data.get('fecha_desde')
        fecha_hasta = form.cleaned_data.get('fecha_hasta')
        cajero = form.cleaned_data.get('cajero')
        metodo_pago = form.cleaned_data.get('metodo_pago')
        estado = form.cleaned_data.get('estado')

        if fecha_desde:
            sales = sales.filter(fecha_hora__date__gte=fecha_desde)

        if fecha_hasta:
            sales = sales.filter(fecha_hora__date__lte=fecha_hasta)

        if cajero:
            sales = sales.filter(cajero=cajero)

        if metodo_pago:
            sales = sales.filter(metodo_pago=metodo_pago)

        if estado:
            sales = sales.filter(estado=estado)

    # Calcular totales usando agregación de base de datos
    from django.db.models import Sum as DBSum, Count
    total_sales = sales.count()
    total_amount = sales.aggregate(total=DBSum('total'))['total'] or Decimal('0.00')

    # Verificar si se solicita exportación
    format_type = request.GET.get('format')
    if format_type == 'pdf':
        return generate_sales_pdf(sales)
    elif format_type == 'excel':
        return generate_sales_excel(sales)

    # Mostrar vista HTML
    context = {
        'form': form,
        'sales': sales[:100],  # Limitar a 100 para la vista HTML
        'total_sales': total_sales,
        'total_amount': total_amount
    }

    return render(request, 'pos/reports/sales_report.html', context)


@login_required
def inventory_report_view(request):
    """Vista para el reporte de inventario con filtros y exportación"""
    from .reports import generate_inventory_pdf, generate_inventory_excel
    from django.db.models import F

    form = InventoryReportFilterForm(request.GET or None)
    products = Product.objects.all()

    # Aplicar filtros
    if form.is_valid():
        categoria = form.cleaned_data.get('categoria')
        genero = form.cleaned_data.get('genero')
        marca = form.cleaned_data.get('marca')
        solo_bajo_stock = form.cleaned_data.get('solo_bajo_stock')
        solo_activos = form.cleaned_data.get('solo_activos')

        if categoria:
            products = products.filter(categoria=categoria)

        if genero:
            products = products.filter(genero=genero)

        if marca:
            products = products.filter(marca__icontains=marca)

        if solo_bajo_stock:
            products = products.filter(stock_actual__lte=F('stock_minimo'))

        if solo_activos:
            products = products.filter(activo=True)

    # Calcular totales usando agregación de base de datos
    from django.db.models import Sum as DBSum, Count, ExpressionWrapper, DecimalField
    total_products = products.count()

    # Contar productos con bajo stock usando la base de datos
    low_stock_count = products.filter(stock_actual__lte=F('stock_minimo')).count()

    # Calcular valor total del inventario
    total_value = products.aggregate(
        total=DBSum(ExpressionWrapper(
            F('precio') * F('stock_actual'),
            output_field=DecimalField()
        ))
    )['total'] or Decimal('0.00')

    # Verificar si se solicita exportación
    format_type = request.GET.get('format')
    if format_type == 'pdf':
        return generate_inventory_pdf(products)
    elif format_type == 'excel':
        return generate_inventory_excel(products)

    # Mostrar vista HTML
    context = {
        'form': form,
        'products': products[:100],  # Limitar a 100 para la vista HTML
        'total_products': total_products,
        'low_stock_count': low_stock_count,
        'total_value': total_value
    }

    return render(request, 'pos/reports/inventory_report.html', context)
