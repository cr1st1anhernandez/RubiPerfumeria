from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    # Vista principal del POS
    path('', views.pos_principal, name='pos_principal'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Gestión de venta temporal (carrito)
    path('buscar-producto/', views.buscar_producto, name='buscar_producto'),
    path('agregar-producto/<int:perfume_id>/', views.agregar_producto, name='agregar_producto'),
    path('actualizar-cantidad/<int:item_id>/', views.actualizar_cantidad, name='actualizar_cantidad'),
    path('eliminar-producto/<int:item_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('aplicar-descuento-producto/<int:item_id>/', views.aplicar_descuento_producto, name='aplicar_descuento_producto'),
    path('limpiar-venta/', views.limpiar_venta, name='limpiar_venta'),

    # Procesamiento de pago
    path('completar-venta/', views.completar_venta, name='completar_venta'),

    # Consulta de ventas
    path('ventas/', views.lista_ventas, name='lista_ventas'),
    path('ventas/<int:venta_id>/', views.detalle_venta, name='detalle_venta'),

    # Devoluciones
    path('ventas/<int:venta_id>/devolver/', views.procesar_devolucion, name='procesar_devolucion'),

    # Generación de ticket PDF
    path('ventas/<int:venta_id>/ticket/', views.generar_ticket_pdf, name='generar_ticket_pdf'),

    # Reportes (para supervisores/administradores)
    path('reportes/', views.reportes_ventas, name='reportes_ventas'),
    path('reportes/inventario/', views.reporte_movimientos_inventario, name='reporte_movimientos'),
]
