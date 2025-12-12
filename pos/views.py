from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum
from accounts.decorators import cajero_required, supervisor_required
from decimal import Decimal
from perfumes.models import Perfume
from .models import Venta, DetalleVenta, MovimientoInventario, VentaTemporal
from .forms import ProcesarPagoForm, DevolucionForm


# ===== VISTA PRINCIPAL DEL POS =====

@cajero_required
def pos_principal(request):
    """
    Vista principal del punto de venta.
    Muestra la interfaz para buscar productos y gestionar la venta actual.
    """
    items_venta = VentaTemporal.objects.filter(cajero=request.user).select_related('perfume')

    # Calcular totales
    subtotal = sum(item.calcular_subtotal() for item in items_venta)
    descuento_general = Decimal(request.session.get('descuento_general', '0'))
    descuento_monto = subtotal * descuento_general / 100
    total = subtotal - descuento_monto

    context = {
        'items_venta': items_venta,
        'subtotal': subtotal,
        'descuento_general': descuento_general,
        'descuento_monto': descuento_monto,
        'total': total,
        'cantidad_items': items_venta.count(),
    }

    return render(request, 'pos/pos_principal.html', context)


# ===== BÚSQUEDA Y GESTIÓN DE PRODUCTOS =====

@cajero_required
def buscar_producto(request):
    """
    Busca productos por código de barras, nombre o marca.
    Responde con JSON para búsqueda AJAX dinámica.
    """
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'productos': []})

    # Buscar por código de barras (exacto) o nombre/marca (contiene)
    productos = Perfume.objects.filter(
        Q(codigo_barras__iexact=query) |
        Q(nombre__icontains=query) |
        Q(marca__icontains=query)
    ).filter(stock__gt=0)[:10]  # Limitar a 10 resultados

    resultado = [{
        'id': p.id,
        'nombre': f"{p.marca} - {p.nombre} ({p.volumen}ml)",
        'codigo_barras': p.codigo_barras or '',
        'precio': str(p.precio),
        'stock': p.stock,
    } for p in productos]

    return JsonResponse({'productos': resultado})


@cajero_required
@require_http_methods(["POST"])
def agregar_producto(request, perfume_id):
    """
    Agrega un producto a la venta temporal del cajero.
    Valida stock disponible antes de agregar.
    """
    perfume = get_object_or_404(Perfume, pk=perfume_id)
    cantidad = int(request.POST.get('cantidad', 1))

    # Verificar si el producto ya está en la venta temporal
    item_existente = VentaTemporal.objects.filter(
        cajero=request.user,
        perfume=perfume
    ).first()

    # Calcular cantidad total
    cantidad_total = cantidad
    if item_existente:
        cantidad_total += item_existente.cantidad

    # Validar stock disponible
    if cantidad_total > perfume.stock:
        messages.error(request, f'Stock insuficiente. Disponible: {perfume.stock} unidades')
        return redirect('pos:pos_principal')

    # Agregar o actualizar item
    if item_existente:
        item_existente.cantidad += cantidad
        item_existente.save()
        messages.success(request, f'Cantidad actualizada: {item_existente.cantidad}x {perfume.nombre}')
    else:
        VentaTemporal.objects.create(
            cajero=request.user,
            perfume=perfume,
            cantidad=cantidad,
            precio_unitario=perfume.precio
        )
        messages.success(request, f'Producto agregado: {cantidad}x {perfume.nombre}')

    return redirect('pos:pos_principal')


@cajero_required
@require_http_methods(["POST"])
def actualizar_cantidad(request, item_id):
    """
    Actualiza la cantidad de un producto en la venta temporal.
    """
    item = get_object_or_404(VentaTemporal, pk=item_id, cajero=request.user)
    nueva_cantidad = int(request.POST.get('cantidad', 1))

    # Validar stock disponible
    if nueva_cantidad > item.perfume.stock:
        messages.error(request, f'Stock insuficiente. Disponible: {item.perfume.stock} unidades')
        return redirect('pos:pos_principal')

    if nueva_cantidad <= 0:
        item.delete()
        messages.info(request, 'Producto eliminado de la venta')
    else:
        item.cantidad = nueva_cantidad
        item.save()
        messages.success(request, 'Cantidad actualizada')

    return redirect('pos:pos_principal')


@cajero_required
@require_http_methods(["POST"])
def eliminar_producto(request, item_id):
    """
    Elimina un producto de la venta temporal.
    """
    item = get_object_or_404(VentaTemporal, pk=item_id, cajero=request.user)
    item.delete()
    messages.info(request, 'Producto eliminado de la venta')
    return redirect('pos:pos_principal')


@cajero_required
@require_http_methods(["POST"])
def aplicar_descuento_producto(request, item_id):
    """
    Aplica un descuento a un producto específico en la venta temporal.
    """
    item = get_object_or_404(VentaTemporal, pk=item_id, cajero=request.user)
    descuento = Decimal(request.POST.get('descuento_porcentaje', '0'))

    if descuento < 0 or descuento > 100:
        messages.error(request, 'El descuento debe estar entre 0 y 100%')
        return redirect('pos:pos_principal')

    item.descuento_porcentaje = descuento
    item.save()
    messages.success(request, f'Descuento de {descuento}% aplicado')
    return redirect('pos:pos_principal')


@cajero_required
@require_http_methods(["POST"])
def limpiar_venta(request):
    """
    Limpia la venta temporal actual (cancela la venta).
    """
    VentaTemporal.objects.filter(cajero=request.user).delete()
    request.session.pop('descuento_general', None)
    messages.info(request, 'Venta cancelada')
    return redirect('pos:pos_principal')


# ===== COMPLETAR VENTA =====

@cajero_required
@require_http_methods(["POST"])
@transaction.atomic
def completar_venta(request):
    """
    Procesa el pago y completa la venta.
    Crea la venta, reduce stock, registra movimientos de inventario
    y limpia la venta temporal.
    """
    items_venta = VentaTemporal.objects.filter(cajero=request.user).select_related('perfume')

    if not items_venta.exists():
        messages.error(request, 'No hay productos en la venta.')
        return redirect('pos:pos_principal')

    # Obtener datos del formulario
    try:
        monto_recibido = Decimal(request.POST.get('monto_recibido', '0'))
        descuento_general = Decimal(request.POST.get('descuento_general', '0'))
    except:
        messages.error(request, 'Datos de pago inválidos')
        return redirect('pos:pos_principal')

    notas = request.POST.get('notas', '').strip()

    # Calcular totales
    subtotal = sum(item.calcular_subtotal() for item in items_venta)
    descuento_monto = subtotal * descuento_general / 100
    total = subtotal - descuento_monto

    # Validar monto recibido
    if monto_recibido < total:
        messages.error(request, f'Monto recibido insuficiente. Total: ${total:.2f}, Recibido: ${monto_recibido:.2f}')
        return redirect('pos:pos_principal')

    cambio = monto_recibido - total

    # Validar stock disponible para todos los items (con bloqueo)
    for item in items_venta:
        perfume = Perfume.objects.select_for_update().get(pk=item.perfume.id)
        if perfume.stock < item.cantidad:
            messages.error(request, f'Stock insuficiente para {perfume.nombre}. Disponible: {perfume.stock}')
            return redirect('pos:pos_principal')

    # Crear venta
    venta = Venta.objects.create(
        cajero=request.user,
        subtotal=subtotal,
        descuento_porcentaje=descuento_general,
        descuento_monto=descuento_monto,
        total=total,
        metodo_pago='EFECTIVO',
        monto_recibido=monto_recibido,
        cambio=cambio,
        estado='COMPLETADA',
        notas=notas
    )

    # Crear detalles de venta y reducir stock
    for item in items_venta:
        # Crear detalle
        DetalleVenta.objects.create(
            venta=venta,
            perfume=item.perfume,
            nombre_producto=str(item.perfume),
            precio_unitario=item.precio_unitario,
            cantidad=item.cantidad,
            descuento_porcentaje=item.descuento_porcentaje
        )

        # Reducir stock con bloqueo
        perfume = Perfume.objects.select_for_update().get(pk=item.perfume.id)
        stock_anterior = perfume.stock
        perfume.stock -= item.cantidad
        perfume.save()

        # Registrar movimiento de inventario
        MovimientoInventario.objects.create(
            perfume=perfume,
            venta=venta,
            usuario=request.user,
            tipo_movimiento='VENTA',
            cantidad=-item.cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=perfume.stock,
            observaciones=f'Venta #{venta.numero_ticket}'
        )

    # Limpiar venta temporal
    items_venta.delete()
    request.session.pop('descuento_general', None)

    messages.success(request, f'✓ Venta completada exitosamente. Ticket: {venta.numero_ticket} | Total: ${total:.2f} | Cambio: ${cambio:.2f}')
    return redirect('pos:detalle_venta', venta_id=venta.id)


# ===== CONSULTA DE VENTAS =====

@cajero_required
def lista_ventas(request):
    """
    Lista todas las ventas realizadas.
    Permite filtrar por fecha, estado y cajero.
    """
    ventas = Venta.objects.select_related('cajero').order_by('-fecha_creacion')

    # Aplicar filtros si existen
    estado = request.GET.get('estado')
    if estado:
        ventas = ventas.filter(estado=estado)

    context = {
        'ventas': ventas[:50],  # Limitar a las últimas 50 ventas
        'estado_seleccionado': estado,
    }

    return render(request, 'pos/lista_ventas.html', context)


@cajero_required
def detalle_venta(request, venta_id):
    """
    Muestra el detalle completo de una venta específica.
    """
    venta = get_object_or_404(
        Venta.objects.select_related('cajero').prefetch_related('detalles__perfume'),
        pk=venta_id
    )

    context = {
        'venta': venta,
        'puede_devolver': venta.puede_ser_devuelta(),
    }

    return render(request, 'pos/detalle_venta.html', context)


# ===== DEVOLUCIONES =====

@cajero_required
@require_http_methods(["POST"])
@transaction.atomic
def procesar_devolucion(request, venta_id):
    """
    Procesa la devolución completa de una venta.
    Restaura el stock y registra movimientos de inventario.
    """
    venta = get_object_or_404(Venta, pk=venta_id)

    # Validar que puede ser devuelta
    if not venta.puede_ser_devuelta():
        messages.error(request, 'Esta venta no puede ser devuelta (estado inválido o fuera del período de 30 días)')
        return redirect('pos:detalle_venta', venta_id=venta_id)

    # Confirmar devolución
    if request.POST.get('confirmar') != 'SI':
        messages.warning(request, 'Devolución cancelada')
        return redirect('pos:detalle_venta', venta_id=venta_id)

    motivo = request.POST.get('motivo', '').strip()

    # Restaurar stock para cada detalle
    for detalle in venta.detalles.all():
        perfume = Perfume.objects.select_for_update().get(pk=detalle.perfume.id)
        stock_anterior = perfume.stock
        perfume.stock += detalle.cantidad
        perfume.save()

        # Registrar movimiento de inventario
        MovimientoInventario.objects.create(
            perfume=perfume,
            venta=venta,
            usuario=request.user,
            tipo_movimiento='DEVOLUCION',
            cantidad=detalle.cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=perfume.stock,
            observaciones=f'Devolución de venta #{venta.numero_ticket}. Motivo: {motivo}'
        )

    # Actualizar estado de la venta
    venta.estado = 'DEVUELTA'
    venta.save()

    messages.success(request, f'✓ Devolución procesada exitosamente. Ticket: {venta.numero_ticket}')
    return redirect('pos:detalle_venta', venta_id=venta_id)


# ===== REPORTES =====

@supervisor_required
def reportes_ventas(request):
    """
    Dashboard con reportes y estadísticas de ventas.
    Solo para supervisores y administradores.
    """
    from django.utils import timezone
    from datetime import timedelta

    hoy = timezone.now().date()
    hace_7_dias = hoy - timedelta(days=7)
    hace_30_dias = hoy - timedelta(days=30)

    # Ventas del día
    ventas_hoy = Venta.objects.filter(
        fecha_creacion__date=hoy,
        estado='COMPLETADA'
    )
    total_hoy = ventas_hoy.aggregate(Sum('total'))['total__sum'] or 0
    cantidad_hoy = ventas_hoy.count()

    # Ventas de la semana
    ventas_semana = Venta.objects.filter(
        fecha_creacion__date__gte=hace_7_dias,
        estado='COMPLETADA'
    )
    total_semana = ventas_semana.aggregate(Sum('total'))['total__sum'] or 0
    cantidad_semana = ventas_semana.count()

    # Ventas del mes
    ventas_mes = Venta.objects.filter(
        fecha_creacion__date__gte=hace_30_dias,
        estado='COMPLETADA'
    )
    total_mes = ventas_mes.aggregate(Sum('total'))['total__sum'] or 0
    cantidad_mes = ventas_mes.count()

    context = {
        'ventas_hoy': cantidad_hoy,
        'total_hoy': total_hoy,
        'ventas_semana': cantidad_semana,
        'total_semana': total_semana,
        'ventas_mes': cantidad_mes,
        'total_mes': total_mes,
    }

    return render(request, 'pos/reportes_ventas.html', context)


@supervisor_required
def reporte_movimientos_inventario(request):
    """
    Muestra el historial de movimientos de inventario.
    Solo para supervisores y administradores.
    """
    movimientos = MovimientoInventario.objects.select_related(
        'perfume', 'usuario', 'venta'
    ).order_by('-fecha_creacion')[:100]

    context = {
        'movimientos': movimientos,
    }

    return render(request, 'pos/reporte_movimientos.html', context)


# ===== GENERACIÓN DE PDF =====

@cajero_required
def generar_ticket_pdf(request, venta_id):
    """
    Genera un ticket en PDF para una venta.
    Formato de ticket térmico de 80mm de ancho.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    venta = get_object_or_404(
        Venta.objects.select_related('cajero').prefetch_related('detalles__perfume'),
        pk=venta_id
    )

    # Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ticket_{venta.numero_ticket}.pdf"'

    # Configurar tamaño de ticket (80mm de ancho, altura variable)
    ancho_ticket = 80 * mm
    alto_ticket = 297 * mm  # Largo máximo (A4)

    # Crear PDF
    p = canvas.Canvas(response, pagesize=(ancho_ticket, alto_ticket))

    # Configuración
    margen = 5 * mm
    y = alto_ticket - margen
    ancho_contenido = ancho_ticket - (2 * margen)

    # Función auxiliar para centrar texto
    def texto_centrado(texto, y_pos, font_size=10, bold=False):
        font = "Helvetica-Bold" if bold else "Helvetica"
        p.setFont(font, font_size)
        ancho_texto = p.stringWidth(texto, font, font_size)
        x = (ancho_ticket - ancho_texto) / 2
        p.drawString(x, y_pos, texto)
        return y_pos - (font_size + 2)

    def texto_izquierda(texto, y_pos, font_size=8):
        p.setFont("Helvetica", font_size)
        p.drawString(margen, y_pos, texto)
        return y_pos - (font_size + 2)

    def texto_derecha(texto, y_pos, font_size=8):
        p.setFont("Helvetica", font_size)
        p.drawRightString(ancho_ticket - margen, y_pos, texto)
        return y_pos - (font_size + 2)

    def linea_separadora(y_pos, estilo="="):
        return texto_centrado(estilo * 40, y_pos, 8)

    # ===== ENCABEZADO =====
    y = texto_centrado("RUBI PERFUMERIA", y, 14, True)
    y -= 3
    y = texto_centrado("Perfumes de Calidad", y, 9)
    y -= 8
    y = linea_separadora(y)
    y -= 5

    # ===== INFORMACIÓN DE TICKET =====
    p.setFont("Helvetica-Bold", 9)
    p.drawString(margen, y, "TICKET DE VENTA")
    y -= 12

    p.setFont("Helvetica", 8)
    p.drawString(margen, y, f"No. Ticket: {venta.numero_ticket}")
    y -= 10

    fecha_str = venta.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')
    p.drawString(margen, y, f"Fecha: {fecha_str}")
    y -= 10

    p.drawString(margen, y, f"Cajero: {venta.cajero.username}")
    y -= 10

    p.drawString(margen, y, f"Estado: {venta.get_estado_display()}")
    y -= 15

    # ===== LÍNEA SEPARADORA =====
    y = linea_separadora(y)
    y -= 8

    # ===== PRODUCTOS =====
    p.setFont("Helvetica-Bold", 8)
    p.drawString(margen, y, "PRODUCTO")
    p.drawRightString(ancho_ticket - margen, y, "IMPORTE")
    y -= 10

    p.setFont("Helvetica", 7)
    for detalle in venta.detalles.all():
        # Nombre del producto (truncar si es muy largo)
        nombre = detalle.nombre_producto[:35]
        p.drawString(margen, y, nombre)
        y -= 8

        # Cantidad x precio
        linea_detalle = f"{detalle.cantidad} x ${detalle.precio_unitario}"
        p.drawString(margen + 5, y, linea_detalle)

        # Subtotal
        p.drawRightString(ancho_ticket - margen, y, f"${detalle.subtotal}")
        y -= 10

        # Descuento en producto (si aplica)
        if detalle.descuento_porcentaje > 0:
            p.setFont("Helvetica", 6)
            p.drawString(margen + 5, y, f"Desc. {detalle.descuento_porcentaje}%: -${detalle.descuento_monto}")
            p.setFont("Helvetica", 7)
            y -= 8

        y -= 2  # Espacio entre productos

    y -= 3
    y = linea_separadora(y, "-")
    y -= 8

    # ===== TOTALES =====
    p.setFont("Helvetica", 9)
    p.drawString(margen, y, "Subtotal:")
    p.drawRightString(ancho_ticket - margen, y, f"${venta.subtotal}")
    y -= 12

    if venta.descuento_porcentaje > 0:
        p.drawString(margen, y, f"Descuento ({venta.descuento_porcentaje}%):")
        p.drawRightString(ancho_ticket - margen, y, f"-${venta.descuento_monto}")
        y -= 12

    p.setFont("Helvetica-Bold", 11)
    p.drawString(margen, y, "TOTAL:")
    p.drawRightString(ancho_ticket - margen, y, f"${venta.total}")
    y -= 18

    # ===== INFORMACIÓN DE PAGO =====
    p.setFont("Helvetica", 9)
    p.drawString(margen, y, f"Método de Pago: {venta.get_metodo_pago_display()}")
    y -= 12

    if venta.metodo_pago == 'EFECTIVO':
        p.drawString(margen, y, "Efectivo Recibido:")
        p.drawRightString(ancho_ticket - margen, y, f"${venta.monto_recibido}")
        y -= 12

        p.drawString(margen, y, "Cambio:")
        p.drawRightString(ancho_ticket - margen, y, f"${venta.cambio}")
        y -= 15

    # ===== PIE DE PÁGINA =====
    y = linea_separadora(y)
    y -= 10
    y = texto_centrado("¡Gracias por su compra!", y, 10, True)
    y -= 8
    y = texto_centrado("Vuelva pronto", y, 8)
    y -= 15

    if venta.notas:
        y = linea_separadora(y, "-")
        y -= 8
        p.setFont("Helvetica", 7)
        p.drawString(margen, y, "Notas:")
        y -= 8
        # Dividir notas en líneas si es muy largo
        max_chars = 45
        notas_lineas = [venta.notas[i:i+max_chars] for i in range(0, len(venta.notas), max_chars)]
        for linea in notas_lineas:
            p.drawString(margen, y, linea)
            y -= 8

    # ===== INFORMACIÓN ADICIONAL =====
    y -= 10
    y = linea_separadora(y, "-")
    y -= 8
    y = texto_centrado("Sistema POS - Rubi Perfumeria", y, 6)
    y -= 6
    y = texto_centrado(f"Ticket generado: {venta.fecha_creacion.strftime('%d/%m/%Y %H:%M')}", y, 6)

    # Finalizar PDF
    p.showPage()
    p.save()

    return response


# ===== DASHBOARD =====

@supervisor_required
def dashboard(request):
    """Dashboard principal para supervisores y administradores con gráficas y análisis."""
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Avg, Count
    import json
    import calendar

    # Fecha actual y rangos
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)
    hace_30_dias = hoy - timedelta(days=30)

    # Calcular mes anterior para comparaciones
    if inicio_mes.month == 1:
        inicio_mes_anterior = inicio_mes.replace(year=inicio_mes.year - 1, month=12)
    else:
        inicio_mes_anterior = inicio_mes.replace(month=inicio_mes.month - 1)

    fin_mes_anterior = inicio_mes - timedelta(days=1)

    # ===== KPIs PRINCIPALES CON COMPARACIÓN =====

    # Ventas de hoy
    total_ventas_hoy = Venta.objects.filter(fecha_creacion__date=hoy).aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    numero_ventas_hoy = Venta.objects.filter(fecha_creacion__date=hoy).count()

    # Ventas de ayer para comparación
    ayer = hoy - timedelta(days=1)
    total_ventas_ayer = Venta.objects.filter(fecha_creacion__date=ayer).aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')

    # Calcular cambio porcentual día
    if total_ventas_ayer > 0:
        cambio_dia = ((total_ventas_hoy - total_ventas_ayer) / total_ventas_ayer) * 100
    else:
        cambio_dia = 100 if total_ventas_hoy > 0 else 0

    # Ventas del mes actual
    total_ventas_mes = Venta.objects.filter(fecha_creacion__date__gte=inicio_mes).aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')
    numero_ventas_mes = Venta.objects.filter(fecha_creacion__date__gte=inicio_mes).count()

    # Ventas del mes anterior
    total_ventas_mes_anterior = Venta.objects.filter(
        fecha_creacion__date__gte=inicio_mes_anterior,
        fecha_creacion__date__lte=fin_mes_anterior
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')

    # Calcular cambio porcentual mes
    if total_ventas_mes_anterior > 0:
        cambio_mes = ((total_ventas_mes - total_ventas_mes_anterior) / total_ventas_mes_anterior) * 100
    else:
        cambio_mes = 100 if total_ventas_mes > 0 else 0

    # Ticket promedio
    ticket_promedio = Venta.objects.filter(fecha_creacion__date__gte=inicio_mes).aggregate(
        promedio=Avg('total')
    )['promedio'] or Decimal('0')

    ticket_promedio_anterior = Venta.objects.filter(
        fecha_creacion__date__gte=inicio_mes_anterior,
        fecha_creacion__date__lte=fin_mes_anterior
    ).aggregate(promedio=Avg('total'))['promedio'] or Decimal('0')

    if ticket_promedio_anterior > 0:
        cambio_ticket = ((ticket_promedio - ticket_promedio_anterior) / ticket_promedio_anterior) * 100
    else:
        cambio_ticket = 100 if ticket_promedio > 0 else 0

    # ===== GRÁFICA: VENTAS POR DÍA (ÚLTIMOS 30 DÍAS) =====
    ventas_por_dia = []
    fechas_grafica = []
    totales_grafica = []

    for i in range(29, -1, -1):
        dia = hoy - timedelta(days=i)
        total_dia = Venta.objects.filter(fecha_creacion__date=dia).aggregate(
            total=Sum('total')
        )['total'] or Decimal('0')

        ventas_por_dia.append({
            'fecha': dia.strftime('%d/%m'),
            'total': float(total_dia)
        })
        fechas_grafica.append(dia.strftime('%d/%m'))
        totales_grafica.append(float(total_dia))

    # ===== GRÁFICA: TOP 10 PRODUCTOS MÁS VENDIDOS =====
    top_productos = DetalleVenta.objects.filter(
        venta__fecha_creacion__date__gte=hace_30_dias
    ).values(
        'perfume__nombre', 'perfume__marca'
    ).annotate(
        cantidad=Sum('cantidad'),
        total_vendido=Sum('subtotal')
    ).order_by('-total_vendido')[:10]

    productos_labels = []
    productos_valores = []
    productos_cantidades = []

    for producto in top_productos:
        label = f"{producto['perfume__marca']} {producto['perfume__nombre']}"
        productos_labels.append(label)
        productos_valores.append(float(producto['total_vendido']))
        productos_cantidades.append(producto['cantidad'])

    # ===== GRÁFICA: VENTAS POR CAJERO (TOP 5) =====
    ventas_por_cajero = Venta.objects.filter(
        fecha_creacion__date__gte=inicio_mes
    ).values(
        'cajero__username'
    ).annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('-total')[:5]

    cajeros_labels = []
    cajeros_valores = []
    cajeros_cantidades = []

    for cajero in ventas_por_cajero:
        cajeros_labels.append(cajero['cajero__username'])
        cajeros_valores.append(float(cajero['total']))
        cajeros_cantidades.append(cajero['cantidad'])

    # ===== GRÁFICA: DISTRIBUCIÓN DE VENTAS POR HORA =====
    ventas_por_hora = Venta.objects.filter(
        fecha_creacion__date__gte=inicio_mes
    ).extra(select={'hora': 'strftime("%%H", fecha_creacion)'}).values('hora').annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('hora')

    horas_labels = [f"{i:02d}:00" for i in range(24)]
    horas_valores = [0] * 24

    for venta in ventas_por_hora:
        hora_idx = int(venta['hora'])
        horas_valores[hora_idx] = float(venta['total'])

    # Stock bajo (productos con menos de 10 unidades)
    productos_stock_bajo = Perfume.objects.filter(stock__lt=10).order_by('stock')[:10]

    # ===== MÉTRICAS ADICIONALES =====
    total_productos_vendidos = DetalleVenta.objects.filter(
        venta__fecha_creacion__date__gte=inicio_mes
    ).aggregate(total=Sum('cantidad'))['total'] or 0

    total_clientes_mes = numero_ventas_mes  # Cada venta representa un cliente

    context = {
        # KPIs principales
        'total_ventas_hoy': total_ventas_hoy,
        'total_ventas_mes': total_ventas_mes,
        'numero_ventas_hoy': numero_ventas_hoy,
        'numero_ventas_mes': numero_ventas_mes,
        'ticket_promedio': ticket_promedio,

        # Comparaciones
        'cambio_dia': round(cambio_dia, 1),
        'cambio_mes': round(cambio_mes, 1),
        'cambio_ticket': round(cambio_ticket, 1),

        # Métricas adicionales
        'total_productos_vendidos': total_productos_vendidos,
        'total_clientes_mes': total_clientes_mes,

        # Datos para gráficas (JSON)
        'fechas_grafica': json.dumps(fechas_grafica),
        'totales_grafica': json.dumps(totales_grafica),
        'productos_labels': json.dumps(productos_labels),
        'productos_valores': json.dumps(productos_valores),
        'productos_cantidades': json.dumps(productos_cantidades),
        'cajeros_labels': json.dumps(cajeros_labels),
        'cajeros_valores': json.dumps(cajeros_valores),
        'cajeros_cantidades': json.dumps(cajeros_cantidades),
        'horas_labels': json.dumps(horas_labels),
        'horas_valores': json.dumps(horas_valores),

        # Stock bajo
        'productos_stock_bajo': productos_stock_bajo,
    }

    return render(request, 'pos/dashboard.html', context)
