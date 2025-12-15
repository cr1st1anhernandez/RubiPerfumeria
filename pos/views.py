from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Avg, Count
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
    Sistema de reportes con filtros de fecha y exportación a PDF/Excel.
    Solo para supervisores y administradores.
    """
    from django.utils import timezone
    from datetime import timedelta, datetime
    from django.db.models import Q

    # Obtener filtros de la request
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    cajero_id = request.GET.get('cajero')
    exportar = request.GET.get('exportar')

    # Si no hay filtros, usar últimos 30 días por defecto
    hoy = timezone.now().date()
    if not fecha_desde:
        fecha_desde = (hoy - timedelta(days=30)).strftime('%Y-%m-%d')
    if not fecha_hasta:
        fecha_hasta = hoy.strftime('%Y-%m-%d')

    # Convertir strings a dates
    try:
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    except:
        fecha_desde_obj = hoy - timedelta(days=30)
        fecha_hasta_obj = hoy

    # Construir query de ventas
    ventas_query = Venta.objects.filter(
        fecha_creacion__date__gte=fecha_desde_obj,
        fecha_creacion__date__lte=fecha_hasta_obj,
        estado='COMPLETADA'
    ).select_related('cajero').prefetch_related('detalles__perfume')

    # Filtrar por cajero si se especifica
    if cajero_id:
        ventas_query = ventas_query.filter(cajero_id=cajero_id)

    # Ordenar por fecha descendente
    ventas = ventas_query.order_by('-fecha_creacion')

    # Calcular totales
    total_ventas = ventas.aggregate(Sum('total'))['total__sum'] or Decimal('0')
    cantidad_ventas = ventas.count()
    ticket_promedio = ventas.aggregate(Avg('total'))['total__avg'] or Decimal('0')

    # Ventas por día en el período
    from django.db.models.functions import TruncDate
    ventas_por_dia = ventas.annotate(
        dia=TruncDate('fecha_creacion')
    ).values('dia').annotate(
        total=Sum('total'),
        cantidad=Count('id')
    ).order_by('dia')

    # Lista de cajeros para el filtro
    cajeros = User.objects.filter(
        profile__rol__in=['CAJERO', 'SUPERVISOR', 'ADMINISTRADOR']
    ).order_by('username')

    # Si se solicita exportación, redirigir a la función correspondiente
    if exportar == 'pdf':
        return generar_reporte_pdf(request, ventas, fecha_desde_obj, fecha_hasta_obj, total_ventas, cantidad_ventas)
    elif exportar == 'excel':
        return generar_reporte_excel(request, ventas, fecha_desde_obj, fecha_hasta_obj, total_ventas, cantidad_ventas)

    context = {
        'ventas': ventas[:100],  # Limitar a 100 para la vista
        'total_ventas': total_ventas,
        'cantidad_ventas': cantidad_ventas,
        'ticket_promedio': ticket_promedio,
        'ventas_por_dia': ventas_por_dia,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'cajero_seleccionado': cajero_id,
        'cajeros': cajeros,
    }

    return render(request, 'pos/reportes_ventas.html', context)


@supervisor_required
def generar_reporte_pdf(request, ventas, fecha_desde, fecha_hasta, total_ventas, cantidad_ventas):
    """Genera un reporte de ventas en formato PDF."""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from io import BytesIO

    # Crear buffer
    buffer = BytesIO()

    # Crear PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    title = Paragraph("Reporte de Ventas - Rubi Perfumería", title_style)
    elements.append(title)

    # Información del período
    periodo_text = f"Período: {fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}"
    periodo = Paragraph(periodo_text, styles['Normal'])
    elements.append(periodo)
    elements.append(Spacer(1, 12))

    # Resumen
    resumen_data = [
        ['Total de Ventas:', f'${total_ventas:,.2f}'],
        ['Cantidad de Transacciones:', str(cantidad_ventas)],
        ['Ticket Promedio:', f'${(total_ventas/cantidad_ventas if cantidad_ventas > 0 else 0):,.2f}']
    ]

    resumen_table = Table(resumen_data, colWidths=[3*inch, 2*inch])
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.white)
    ]))

    elements.append(resumen_table)
    elements.append(Spacer(1, 20))

    # Detalle de ventas
    subtitle = Paragraph("Detalle de Ventas", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 12))

    # Tabla de ventas (limitada a primeras 50)
    ventas_data = [['Fecha', 'Ticket', 'Cajero', 'Total']]

    for venta in ventas[:50]:
        ventas_data.append([
            venta.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            venta.numero_ticket,
            venta.cajero.username,
            f'${venta.total:,.2f}'
        ])

    ventas_table = Table(ventas_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    ventas_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))

    elements.append(ventas_table)

    if cantidad_ventas > 50:
        nota = Paragraph(f"<i>Mostrando las primeras 50 de {cantidad_ventas} ventas</i>", styles['Normal'])
        elements.append(Spacer(1, 12))
        elements.append(nota)

    # Construir PDF
    doc.build(elements)

    # Preparar respuesta
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"reporte_ventas_{fecha_desde}_{fecha_hasta}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@supervisor_required
def generar_reporte_excel(request, ventas, fecha_desde, fecha_hasta, total_ventas, cantidad_ventas):
    """Genera un reporte de ventas en formato Excel."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte de Ventas"

    # Estilos
    header_font = Font(name='Arial', size=14, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='3498DB', end_color='3498DB', fill_type='solid')

    title_font = Font(name='Arial', size=16, bold=True)
    subtitle_font = Font(name='Arial', size=12, bold=True)

    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Título
    ws['A1'] = 'Reporte de Ventas - Rubi Perfumería'
    ws['A1'].font = title_font
    ws['A1'].alignment = Alignment(horizontal='center')
    ws.merge_cells('A1:F1')

    # Período
    ws['A3'] = 'Período:'
    ws['B3'] = f"{fecha_desde.strftime('%d/%m/%Y')} - {fecha_hasta.strftime('%d/%m/%Y')}"
    ws['A3'].font = Font(bold=True)

    # Resumen
    ws['A5'] = 'Resumen'
    ws['A5'].font = subtitle_font

    ws['A6'] = 'Total de Ventas:'
    ws['B6'] = float(total_ventas)
    ws['B6'].number_format = '$#,##0.00'

    ws['A7'] = 'Cantidad de Transacciones:'
    ws['B7'] = cantidad_ventas

    ws['A8'] = 'Ticket Promedio:'
    ws['B8'] = float(total_ventas / cantidad_ventas if cantidad_ventas > 0 else 0)
    ws['B8'].number_format = '$#,##0.00'

    # Detalle de ventas
    ws['A10'] = 'Detalle de Ventas'
    ws['A10'].font = subtitle_font

    # Encabezados de tabla
    headers = ['Fecha', 'Hora', 'Ticket', 'Cajero', 'Subtotal', 'Descuento', 'Total', 'Estado']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=12, column=col)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    # Datos
    row = 13
    for venta in ventas:
        ws.cell(row=row, column=1).value = venta.fecha_creacion.strftime('%d/%m/%Y')
        ws.cell(row=row, column=2).value = venta.fecha_creacion.strftime('%H:%M:%S')
        ws.cell(row=row, column=3).value = venta.numero_ticket
        ws.cell(row=row, column=4).value = venta.cajero.username
        ws.cell(row=row, column=5).value = float(venta.subtotal)
        ws.cell(row=row, column=6).value = float(venta.descuento_monto)
        ws.cell(row=row, column=7).value = float(venta.total)
        ws.cell(row=row, column=8).value = venta.get_estado_display()

        # Formato
        ws.cell(row=row, column=5).number_format = '$#,##0.00'
        ws.cell(row=row, column=6).number_format = '$#,##0.00'
        ws.cell(row=row, column=7).number_format = '$#,##0.00'

        # Bordes
        for col in range(1, 9):
            ws.cell(row=row, column=col).border = border

        row += 1

    # Ajustar anchos de columna
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 12
    ws.column_dimensions['H'].width = 12

    # Guardar en buffer
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    # Preparar respuesta
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"reporte_ventas_{fecha_desde}_{fecha_hasta}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@supervisor_required
def generar_reporte_inventario_pdf(request, movimientos, productos_stock):
    """Genera un reporte de inventario en formato PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from io import BytesIO
    from django.utils import timezone

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    title = Paragraph("Reporte de Inventario - Rubi Perfumería", title_style)
    elements.append(title)

    fecha_texto = f"Generado: {timezone.now().strftime('%d/%m/%Y %H:%M')}"
    fecha = Paragraph(fecha_texto, styles['Normal'])
    elements.append(fecha)
    elements.append(Spacer(1, 20))

    # Stock Actual
    subtitle = Paragraph("Stock Actual de Productos", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 12))

    stock_data = [['Producto', 'Marca', 'Stock', 'Precio']]
    for producto in productos_stock:
        stock_data.append([
            producto.nombre,
            producto.marca,
            str(producto.stock),
            f'${producto.precio:,.2f}'
        ])

    stock_table = Table(stock_data, colWidths=[2.5*inch, 1.5*inch, 1*inch, 1.5*inch])
    stock_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))

    elements.append(stock_table)
    elements.append(PageBreak())

    # Movimientos
    subtitle2 = Paragraph("Últimos Movimientos de Inventario", styles['Heading2'])
    elements.append(subtitle2)
    elements.append(Spacer(1, 12))

    mov_data = [['Fecha', 'Producto', 'Tipo', 'Cantidad', 'Usuario']]
    for mov in movimientos[:50]:
        mov_data.append([
            mov.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            f"{mov.perfume.marca} {mov.perfume.nombre}",
            mov.get_tipo_display(),
            str(mov.cantidad),
            mov.usuario.username
        ])

    mov_table = Table(mov_data, colWidths=[1.5*inch, 2*inch, 1.2*inch, 1*inch, 1*inch])
    mov_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))

    elements.append(mov_table)

    if movimientos.count() > 50:
        nota = Paragraph(f"<i>Mostrando los primeros 50 de {movimientos.count()} movimientos</i>", styles['Normal'])
        elements.append(Spacer(1, 12))
        elements.append(nota)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"reporte_inventario_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@supervisor_required
def generar_reporte_inventario_excel(request, movimientos, productos_stock):
    """Genera un reporte de inventario en formato Excel."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from io import BytesIO
    from django.utils import timezone

    wb = openpyxl.Workbook()

    # Hoja 1: Stock Actual
    ws_stock = wb.active
    ws_stock.title = "Stock Actual"

    header_font = Font(name='Arial', size=14, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='3498DB', end_color='3498DB', fill_type='solid')
    title_font = Font(name='Arial', size=16, bold=True)
    subtitle_font = Font(name='Arial', size=12, bold=True)

    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Título
    ws_stock['A1'] = 'Reporte de Inventario - Rubi Perfumería'
    ws_stock['A1'].font = title_font
    ws_stock['A1'].alignment = Alignment(horizontal='center')
    ws_stock.merge_cells('A1:F1')

    ws_stock['A3'] = 'Fecha:'
    ws_stock['B3'] = timezone.now().strftime('%d/%m/%Y %H:%M')
    ws_stock['A3'].font = Font(bold=True)

    # Encabezados
    ws_stock['A5'] = 'Stock Actual de Productos'
    ws_stock['A5'].font = subtitle_font

    headers = ['Producto', 'Marca', 'Tipo', 'Volumen (ml)', 'Stock', 'Precio Unitario', 'Valor Total']
    for col, header in enumerate(headers, start=1):
        cell = ws_stock.cell(row=7, column=col)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    # Datos
    row = 8
    total_valor = 0
    for producto in productos_stock:
        valor_total = float(producto.precio) * producto.stock
        total_valor += valor_total

        ws_stock.cell(row=row, column=1).value = producto.nombre
        ws_stock.cell(row=row, column=2).value = producto.marca
        ws_stock.cell(row=row, column=3).value = producto.tipo
        ws_stock.cell(row=row, column=4).value = producto.volumen
        ws_stock.cell(row=row, column=5).value = producto.stock
        ws_stock.cell(row=row, column=6).value = float(producto.precio)
        ws_stock.cell(row=row, column=7).value = valor_total

        # Formato
        ws_stock.cell(row=row, column=6).number_format = '$#,##0.00'
        ws_stock.cell(row=row, column=7).number_format = '$#,##0.00'

        # Bordes
        for col in range(1, 8):
            ws_stock.cell(row=row, column=col).border = border

        row += 1

    # Total
    ws_stock.cell(row=row, column=6).value = 'TOTAL:'
    ws_stock.cell(row=row, column=6).font = Font(bold=True)
    ws_stock.cell(row=row, column=7).value = total_valor
    ws_stock.cell(row=row, column=7).number_format = '$#,##0.00'
    ws_stock.cell(row=row, column=7).font = Font(bold=True)

    # Ajustar anchos
    ws_stock.column_dimensions['A'].width = 25
    ws_stock.column_dimensions['B'].width = 20
    ws_stock.column_dimensions['C'].width = 10
    ws_stock.column_dimensions['D'].width = 12
    ws_stock.column_dimensions['E'].width = 10
    ws_stock.column_dimensions['F'].width = 15
    ws_stock.column_dimensions['G'].width = 15

    # Hoja 2: Movimientos
    ws_mov = wb.create_sheet(title="Movimientos")

    ws_mov['A1'] = 'Movimientos de Inventario'
    ws_mov['A1'].font = title_font
    ws_mov['A1'].alignment = Alignment(horizontal='center')
    ws_mov.merge_cells('A1:F1')

    headers_mov = ['Fecha', 'Hora', 'Producto', 'Marca', 'Tipo Movimiento', 'Cantidad', 'Usuario']
    for col, header in enumerate(headers_mov, start=1):
        cell = ws_mov.cell(row=3, column=col)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border

    row = 4
    for mov in movimientos:
        ws_mov.cell(row=row, column=1).value = mov.fecha_creacion.strftime('%d/%m/%Y')
        ws_mov.cell(row=row, column=2).value = mov.fecha_creacion.strftime('%H:%M:%S')
        ws_mov.cell(row=row, column=3).value = mov.perfume.nombre
        ws_mov.cell(row=row, column=4).value = mov.perfume.marca
        ws_mov.cell(row=row, column=5).value = mov.get_tipo_display()
        ws_mov.cell(row=row, column=6).value = mov.cantidad
        ws_mov.cell(row=row, column=7).value = mov.usuario.username

        # Bordes
        for col in range(1, 8):
            ws_mov.cell(row=row, column=col).border = border

        row += 1

    # Ajustar anchos
    ws_mov.column_dimensions['A'].width = 12
    ws_mov.column_dimensions['B'].width = 10
    ws_mov.column_dimensions['C'].width = 25
    ws_mov.column_dimensions['D'].width = 20
    ws_mov.column_dimensions['E'].width = 18
    ws_mov.column_dimensions['F'].width = 10
    ws_mov.column_dimensions['G'].width = 15

    # Guardar
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"reporte_inventario_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@supervisor_required
def reporte_movimientos_inventario(request):
    """
    Reporte de movimientos de inventario con exportación a PDF/Excel.
    Solo para supervisores y administradores.
    """
    exportar = request.GET.get('exportar')

    # Obtener todos los movimientos (sin límite para exportación)
    movimientos = MovimientoInventario.objects.select_related(
        'perfume', 'usuario', 'venta'
    ).order_by('-fecha_creacion')

    # Obtener stock actual de todos los productos
    productos_stock = Perfume.objects.all().order_by('nombre')

    # Si se solicita exportación
    if exportar == 'pdf':
        return generar_reporte_inventario_pdf(request, movimientos, productos_stock)
    elif exportar == 'excel':
        return generar_reporte_inventario_excel(request, movimientos, productos_stock)

    context = {
        'movimientos': movimientos[:100],  # Limitar a 100 para la vista
        'total_movimientos': movimientos.count(),
        'productos_stock': productos_stock,
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
