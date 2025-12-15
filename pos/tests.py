from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from .models import Venta, DetalleVenta, MovimientoInventario, VentaTemporal
from perfumes.models import Perfume
from accounts.models import UserProfile


class BaseTestCase(TestCase):
    """Base test case con datos de prueba comunes."""

    def setUp(self):
        """Configurar datos de prueba."""
        # Crear usuarios (el perfil se crea automáticamente por señal)
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='testpass123',
            email='admin@test.com'
        )
        # Actualizar el perfil creado automáticamente
        self.admin_profile = self.admin_user.profile
        self.admin_profile.rol = 'ADMINISTRADOR'
        self.admin_profile.save()

        self.supervisor_user = User.objects.create_user(
            username='supervisor_test',
            password='testpass123',
            email='supervisor@test.com'
        )
        self.supervisor_profile = self.supervisor_user.profile
        self.supervisor_profile.rol = 'SUPERVISOR'
        self.supervisor_profile.save()

        self.cajero_user = User.objects.create_user(
            username='cajero_test',
            password='testpass123',
            email='cajero@test.com'
        )
        self.cajero_profile = self.cajero_user.profile
        self.cajero_profile.rol = 'CAJERO'
        self.cajero_profile.save()

        # Crear perfumes de prueba
        self.perfume1 = Perfume.objects.create(
            nombre='Fragancia Test 1',
            marca='Marca Test',
            tipo='EDP',
            genero='U',
            notas_superiores='Bergamota',
            notas_medias='Jazmin',
            notas_base='Almizcle',
            volumen=100,
            precio=Decimal('1500.00'),
            stock=10,
            codigo_barras='TEST001'
        )

        self.perfume2 = Perfume.objects.create(
            nombre='Fragancia Test 2',
            marca='Marca Test',
            tipo='EDT',
            genero='M',
            notas_superiores='Limon',
            notas_medias='Rosa',
            notas_base='Vainilla',
            volumen=50,
            precio=Decimal('800.00'),
            stock=5,
            codigo_barras='TEST002'
        )

        self.perfume_sin_stock = Perfume.objects.create(
            nombre='Fragancia Sin Stock',
            marca='Marca Test',
            tipo='EDC',
            genero='F',
            notas_superiores='Naranja',
            notas_medias='Lavanda',
            notas_base='Cedro',
            volumen=75,
            precio=Decimal('1200.00'),
            stock=0,
            codigo_barras='TEST003'
        )


# ============================================================
# TESTS UNITARIOS - MODELOS
# ============================================================

class VentaModelTest(BaseTestCase):
    """Tests unitarios para el modelo Venta."""

    def test_crear_venta(self):
        """Test crear una venta básica."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00')
        )

        self.assertIsNotNone(venta.numero_ticket)
        self.assertEqual(venta.estado, 'COMPLETADA')
        self.assertEqual(venta.metodo_pago, 'EFECTIVO')

    def test_generar_numero_ticket(self):
        """Test generación automática de número de ticket."""
        venta1 = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('0.00')
        )

        venta2 = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            monto_recibido=Decimal('500.00'),
            cambio=Decimal('0.00')
        )

        # Verificar formato
        self.assertRegex(venta1.numero_ticket, r'\d{8}-\d{5}')
        self.assertRegex(venta2.numero_ticket, r'\d{8}-\d{5}')

        # Verificar secuencia
        fecha_hoy = timezone.now().strftime('%Y%m%d')
        self.assertTrue(venta1.numero_ticket.startswith(fecha_hoy))
        self.assertTrue(venta2.numero_ticket.startswith(fecha_hoy))

        # Verificar unicidad
        self.assertNotEqual(venta1.numero_ticket, venta2.numero_ticket)

    def test_calcular_totales(self):
        """Test cálculo de totales con descuento."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1000.00'),
            descuento_porcentaje=Decimal('10.00'),
            total=Decimal('900.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('100.00')
        )

        # Crear detalles
        DetalleVenta.objects.create(
            venta=venta,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=Decimal('1000.00'),
            subtotal=Decimal('1000.00')
        )

        # Calcular totales
        total = venta.calcular_totales()

        self.assertEqual(venta.subtotal, Decimal('1000.00'))
        self.assertEqual(venta.descuento_monto, Decimal('100.00'))
        self.assertEqual(venta.total, Decimal('900.00'))
        self.assertEqual(total, Decimal('900.00'))

    def test_puede_ser_devuelta_dentro_periodo(self):
        """Test verificar si venta puede ser devuelta dentro de 30 días."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('0.00'),
            estado='COMPLETADA'
        )

        self.assertTrue(venta.puede_ser_devuelta())

    def test_no_puede_ser_devuelta_fuera_periodo(self):
        """Test verificar que no se puede devolver después de 30 días."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('0.00'),
            estado='COMPLETADA'
        )

        # Simular que la venta fue hace 31 días
        venta.fecha_creacion = timezone.now() - timedelta(days=31)
        venta.save()

        self.assertFalse(venta.puede_ser_devuelta())

    def test_no_puede_ser_devuelta_cancelada(self):
        """Test verificar que venta cancelada no puede ser devuelta."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('0.00'),
            estado='CANCELADA'
        )

        self.assertFalse(venta.puede_ser_devuelta())


class DetalleVentaModelTest(BaseTestCase):
    """Tests unitarios para el modelo DetalleVenta."""

    def test_crear_detalle_venta(self):
        """Test crear detalle de venta."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00')
        )

        detalle = DetalleVenta.objects.create(
            venta=venta,
            perfume=self.perfume1,
            cantidad=2,
            precio_unitario=Decimal('750.00')
        )

        self.assertEqual(detalle.nombre_producto, str(self.perfume1))
        self.assertEqual(detalle.precio_unitario, Decimal('750.00'))
        self.assertEqual(detalle.subtotal, Decimal('1500.00'))

    def test_calcular_subtotal_sin_descuento(self):
        """Test calcular subtotal sin descuento."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('3000.00'),
            total=Decimal('3000.00'),
            monto_recibido=Decimal('3000.00'),
            cambio=Decimal('0.00')
        )

        detalle = DetalleVenta(
            venta=venta,
            perfume=self.perfume1,
            cantidad=2,
            precio_unitario=Decimal('1500.00')
        )

        subtotal = detalle.calcular_subtotal()

        self.assertEqual(subtotal, Decimal('3000.00'))
        self.assertEqual(detalle.descuento_monto, Decimal('0.00'))

    def test_calcular_subtotal_con_descuento(self):
        """Test calcular subtotal con descuento."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('2700.00'),
            total=Decimal('2700.00'),
            monto_recibido=Decimal('3000.00'),
            cambio=Decimal('300.00')
        )

        detalle = DetalleVenta(
            venta=venta,
            perfume=self.perfume1,
            cantidad=2,
            precio_unitario=Decimal('1500.00'),
            descuento_porcentaje=Decimal('10.00')
        )

        subtotal = detalle.calcular_subtotal()

        self.assertEqual(detalle.descuento_monto, Decimal('300.00'))
        self.assertEqual(subtotal, Decimal('2700.00'))


class VentaTemporalModelTest(BaseTestCase):
    """Tests unitarios para el modelo VentaTemporal."""

    def test_crear_venta_temporal(self):
        """Test crear item temporal."""
        item = VentaTemporal.objects.create(
            cajero=self.cajero_user,
            perfume=self.perfume1,
            cantidad=2,
            precio_unitario=self.perfume1.precio
        )

        self.assertEqual(item.cantidad, 2)
        self.assertEqual(item.precio_unitario, Decimal('1500.00'))

    def test_calcular_subtotal_temporal(self):
        """Test calcular subtotal de item temporal."""
        item = VentaTemporal.objects.create(
            cajero=self.cajero_user,
            perfume=self.perfume1,
            cantidad=3,
            precio_unitario=Decimal('1000.00'),
            descuento_porcentaje=Decimal('10.00')
        )

        subtotal = item.calcular_subtotal()

        self.assertEqual(subtotal, Decimal('2700.00'))

    def test_unique_together_cajero_perfume(self):
        """Test que no se puede agregar el mismo perfume dos veces por cajero."""
        VentaTemporal.objects.create(
            cajero=self.cajero_user,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=self.perfume1.precio
        )

        # Intentar crear otro con el mismo cajero y perfume debe fallar
        with self.assertRaises(Exception):
            VentaTemporal.objects.create(
                cajero=self.cajero_user,
                perfume=self.perfume1,
                cantidad=2,
                precio_unitario=self.perfume1.precio
            )


class MovimientoInventarioModelTest(BaseTestCase):
    """Tests unitarios para el modelo MovimientoInventario."""

    def test_crear_movimiento_venta(self):
        """Test crear movimiento de inventario por venta."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00')
        )

        movimiento = MovimientoInventario.objects.create(
            perfume=self.perfume1,
            venta=venta,
            usuario=self.cajero_user,
            tipo_movimiento='VENTA',
            cantidad=-2,
            stock_anterior=10,
            stock_nuevo=8
        )

        self.assertEqual(movimiento.tipo_movimiento, 'VENTA')
        self.assertEqual(movimiento.cantidad, -2)
        self.assertEqual(movimiento.stock_nuevo, 8)

    def test_crear_movimiento_devolucion(self):
        """Test crear movimiento de devolución."""
        venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00')
        )

        movimiento = MovimientoInventario.objects.create(
            perfume=self.perfume1,
            venta=venta,
            usuario=self.cajero_user,
            tipo_movimiento='DEVOLUCION',
            cantidad=2,
            stock_anterior=8,
            stock_nuevo=10,
            observaciones='Devolucion de venta'
        )

        self.assertEqual(movimiento.tipo_movimiento, 'DEVOLUCION')
        self.assertEqual(movimiento.cantidad, 2)
        self.assertTrue(movimiento.cantidad > 0)


# ============================================================
# TESTS DE DJANGO CLIENT - VISTAS
# ============================================================

class POSViewsTest(BaseTestCase):
    """Tests de vistas del POS usando Django Client."""

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_pos_principal_requiere_login(self):
        """Test que POS principal requiere autenticación."""
        response = self.client.get(reverse('pos:pos_principal'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_pos_principal_acceso_cajero(self):
        """Test que cajero puede acceder al POS."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(reverse('pos:pos_principal'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/pos_principal.html')

    def test_buscar_producto_ajax(self):
        """Test búsqueda AJAX de productos."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(
            reverse('pos:buscar_producto'),
            {'q': 'Test 1'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = response.json()
        self.assertIn('productos', data)
        self.assertGreater(len(data['productos']), 0)

    def test_agregar_producto_a_venta(self):
        """Test agregar producto a venta temporal."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.post(
            reverse('pos:agregar_producto', args=[self.perfume1.id]),
            {'cantidad': 2}
        )

        self.assertEqual(response.status_code, 302)

        # Verificar que se creó el item temporal
        item = VentaTemporal.objects.filter(
            cajero=self.cajero_user,
            perfume=self.perfume1
        ).first()

        self.assertIsNotNone(item)
        self.assertEqual(item.cantidad, 2)

    def test_no_agregar_producto_sin_stock(self):
        """Test que no se puede agregar producto sin stock."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.post(
            reverse('pos:agregar_producto', args=[self.perfume_sin_stock.id]),
            {'cantidad': 1}
        )

        # Debe redirigir con mensaje de error
        self.assertEqual(response.status_code, 302)

        # No debe haberse creado el item
        item_count = VentaTemporal.objects.filter(
            cajero=self.cajero_user,
            perfume=self.perfume_sin_stock
        ).count()

        self.assertEqual(item_count, 0)

    def test_actualizar_cantidad(self):
        """Test actualizar cantidad de producto en venta."""
        self.client.login(username='cajero_test', password='testpass123')

        # Crear item temporal
        item = VentaTemporal.objects.create(
            cajero=self.cajero_user,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=self.perfume1.precio
        )

        # Actualizar cantidad
        response = self.client.post(
            reverse('pos:actualizar_cantidad', args=[item.id]),
            {'cantidad': 3}
        )

        self.assertEqual(response.status_code, 302)

        # Verificar actualización
        item.refresh_from_db()
        self.assertEqual(item.cantidad, 3)

    def test_eliminar_producto_de_venta(self):
        """Test eliminar producto de venta temporal."""
        self.client.login(username='cajero_test', password='testpass123')

        # Crear item temporal
        item = VentaTemporal.objects.create(
            cajero=self.cajero_user,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=self.perfume1.precio
        )

        # Eliminar
        response = self.client.post(
            reverse('pos:eliminar_producto', args=[item.id])
        )

        self.assertEqual(response.status_code, 302)

        # Verificar eliminación
        item_exists = VentaTemporal.objects.filter(id=item.id).exists()
        self.assertFalse(item_exists)


class CompletarVentaTest(TransactionTestCase):
    """Tests para completar ventas (requiere TransactionTestCase para select_for_update)."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.cajero_user = User.objects.create_user(
            username='cajero_test',
            password='testpass123'
        )
        # Actualizar perfil creado automáticamente
        self.cajero_user.profile.rol = 'CAJERO'
        self.cajero_user.profile.save()

        self.perfume = Perfume.objects.create(
            nombre='Test Perfume',
            marca='Test Brand',
            tipo='EDP',
            genero='U',
            notas_superiores='Test',
            notas_medias='Test',
            notas_base='Test',
            volumen=100,
            precio=Decimal('1000.00'),
            stock=10
        )

        self.client = Client()
        self.client.login(username='cajero_test', password='testpass123')

    def test_completar_venta_exitosa(self):
        """Test completar venta reduce stock y crea registros."""
        # Agregar producto a venta temporal
        VentaTemporal.objects.create(
            cajero=self.cajero_user,
            perfume=self.perfume,
            cantidad=2,
            precio_unitario=self.perfume.precio
        )

        # Completar venta
        response = self.client.post(
            reverse('pos:completar_venta'),
            {
                'monto_recibido': '2500.00',
                'descuento_general': '0'
            }
        )

        self.assertEqual(response.status_code, 302)

        # Verificar que se creó la venta
        venta = Venta.objects.filter(cajero=self.cajero_user).first()
        self.assertIsNotNone(venta)
        self.assertEqual(venta.total, Decimal('2000.00'))

        # Verificar que se redujo el stock
        self.perfume.refresh_from_db()
        self.assertEqual(self.perfume.stock, 8)

        # Verificar movimiento de inventario
        movimiento = MovimientoInventario.objects.filter(
            perfume=self.perfume,
            tipo_movimiento='VENTA'
        ).first()
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.cantidad, -2)

        # Verificar que se limpió la venta temporal
        items_temporales = VentaTemporal.objects.filter(cajero=self.cajero_user).count()
        self.assertEqual(items_temporales, 0)

    def test_completar_venta_sin_items(self):
        """Test que no se puede completar venta sin productos."""
        response = self.client.post(
            reverse('pos:completar_venta'),
            {
                'monto_recibido': '100.00',
                'descuento_general': '0'
            }
        )

        # Debe redirigir con error
        self.assertEqual(response.status_code, 302)

        # No debe haberse creado venta
        ventas_count = Venta.objects.filter(cajero=self.cajero_user).count()
        self.assertEqual(ventas_count, 0)


class ListaVentasViewTest(BaseTestCase):
    """Tests para la vista de lista de ventas."""

    def setUp(self):
        super().setUp()
        self.client = Client()

        # Crear ventas de prueba
        self.venta1 = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1000.00'),
            total=Decimal('1000.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('0.00'),
            estado='COMPLETADA'
        )

        self.venta2 = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
            monto_recibido=Decimal('500.00'),
            cambio=Decimal('0.00'),
            estado='CANCELADA'
        )

    def test_lista_ventas_requiere_login(self):
        """Test que lista de ventas requiere autenticación."""
        response = self.client.get(reverse('pos:lista_ventas'))
        self.assertEqual(response.status_code, 302)

    def test_lista_ventas_muestra_todas(self):
        """Test que muestra todas las ventas."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(reverse('pos:lista_ventas'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['ventas']), 2)

    def test_filtrar_ventas_por_estado(self):
        """Test filtrar ventas por estado."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(
            reverse('pos:lista_ventas'),
            {'estado': 'COMPLETADA'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['ventas']), 1)
        self.assertEqual(response.context['ventas'][0].estado, 'COMPLETADA')


class DetalleVentaViewTest(BaseTestCase):
    """Tests para la vista de detalle de venta."""

    def setUp(self):
        super().setUp()
        self.client = Client()

        # Crear venta con detalles
        self.venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00')
        )

        DetalleVenta.objects.create(
            venta=self.venta,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=self.perfume1.precio,
            subtotal=Decimal('1500.00')
        )

    def test_detalle_venta_requiere_login(self):
        """Test que detalle requiere autenticación."""
        response = self.client.get(
            reverse('pos:detalle_venta', args=[self.venta.id])
        )
        self.assertEqual(response.status_code, 302)

    def test_detalle_venta_muestra_informacion(self):
        """Test que muestra información de la venta."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(
            reverse('pos:detalle_venta', args=[self.venta.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['venta'], self.venta)
        self.assertIn('puede_devolver', response.context)


class ProcesarDevolucionTest(TransactionTestCase):
    """Tests para procesar devoluciones."""

    def setUp(self):
        """Configurar datos de prueba."""
        self.cajero_user = User.objects.create_user(
            username='cajero_test',
            password='testpass123'
        )
        # Actualizar perfil creado automáticamente
        self.cajero_user.profile.rol = 'CAJERO'
        self.cajero_user.profile.save()

        self.perfume = Perfume.objects.create(
            nombre='Test Perfume',
            marca='Test Brand',
            tipo='EDP',
            genero='U',
            notas_superiores='Test',
            notas_medias='Test',
            notas_base='Test',
            volumen=100,
            precio=Decimal('1000.00'),
            stock=8
        )

        self.venta = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('0.00'),
            estado='COMPLETADA'
        )

        DetalleVenta.objects.create(
            venta=self.venta,
            perfume=self.perfume,
            cantidad=2,
            precio_unitario=Decimal('1000.00'),
            subtotal=Decimal('2000.00')
        )

        self.client = Client()
        self.client.login(username='cajero_test', password='testpass123')

    def test_procesar_devolucion_exitosa(self):
        """Test procesar devolución restaura stock."""
        response = self.client.post(
            reverse('pos:procesar_devolucion', args=[self.venta.id]),
            {
                'confirmar': 'SI',
                'motivo': 'Cliente insatisfecho'
            }
        )

        self.assertEqual(response.status_code, 302)

        # Verificar estado de venta
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, 'DEVUELTA')

        # Verificar que se restauró el stock
        self.perfume.refresh_from_db()
        self.assertEqual(self.perfume.stock, 10)

        # Verificar movimiento de inventario
        movimiento = MovimientoInventario.objects.filter(
            perfume=self.perfume,
            tipo_movimiento='DEVOLUCION'
        ).first()
        self.assertIsNotNone(movimiento)
        self.assertEqual(movimiento.cantidad, 2)


class RoleBasedAccessTest(BaseTestCase):
    """Tests para control de acceso basado en roles."""

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_cajero_no_puede_acceder_inventario(self):
        """Test que cajero no puede acceder al inventario."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(reverse('perfume_list'))

        # Debe redirigir
        self.assertEqual(response.status_code, 302)

    def test_supervisor_puede_acceder_inventario(self):
        """Test que supervisor puede acceder al inventario."""
        self.client.login(username='supervisor_test', password='testpass123')
        response = self.client.get(reverse('perfume_list'))

        self.assertEqual(response.status_code, 200)

    def test_cajero_puede_acceder_pos(self):
        """Test que cajero puede acceder al POS."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(reverse('pos:pos_principal'))

        self.assertEqual(response.status_code, 200)

    def test_cajero_no_puede_acceder_reportes(self):
        """Test que cajero no puede acceder a reportes."""
        self.client.login(username='cajero_test', password='testpass123')
        response = self.client.get(reverse('pos:reportes_ventas'))

        # Debe redirigir
        self.assertEqual(response.status_code, 302)

    def test_supervisor_puede_acceder_reportes(self):
        """Test que supervisor puede acceder a reportes."""
        self.client.login(username='supervisor_test', password='testpass123')
        response = self.client.get(reverse('pos:reportes_ventas'))

        self.assertEqual(response.status_code, 200)


class LoginRedirectTest(BaseTestCase):
    """Tests para redirección por rol al hacer login."""

    def test_cajero_redirige_a_pos(self):
        """Test que cajero se redirige al POS al hacer login."""
        response = self.client.post(
            reverse('login'),
            {
                'username': 'cajero_test',
                'password': 'testpass123'
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('pos:pos_principal'))

    def test_supervisor_redirige_a_reportes(self):
        """Test que supervisor se redirige a reportes al hacer login."""
        response = self.client.post(
            reverse('login'),
            {
                'username': 'supervisor_test',
                'password': 'testpass123'
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('pos:reportes_ventas'))

    def test_admin_redirige_a_home(self):
        """Test que admin se redirige a home al hacer login."""
        response = self.client.post(
            reverse('login'),
            {
                'username': 'admin_test',
                'password': 'testpass123'
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))
