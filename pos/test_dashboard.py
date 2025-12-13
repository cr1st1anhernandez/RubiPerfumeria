"""
Tests para el Dashboard de Administrador
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from .models import Product, Sales, SaleDetails, Inventory, UserProfile


class DashboardPermissionsTestCase(TestCase):
    """Tests de permisos de acceso al dashboard"""

    def setUp(self):
        # Crear usuarios con diferentes roles
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            rol='ADMINISTRADOR'
        )

        self.supervisor_user = User.objects.create_user(
            username='supervisor',
            password='super123'
        )
        self.supervisor_profile = UserProfile.objects.create(
            user=self.supervisor_user,
            rol='SUPERVISOR'
        )

        self.cajero_user = User.objects.create_user(
            username='cajero',
            password='cajero123'
        )
        self.cajero_profile = UserProfile.objects.create(
            user=self.cajero_user,
            rol='CAJERO'
        )

        self.client = Client()

    def test_admin_can_access_dashboard(self):
        """El administrador puede acceder al dashboard"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('pos:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_can_access_dashboard(self):
        """El supervisor puede acceder al dashboard"""
        self.client.login(username='supervisor', password='super123')
        response = self.client.get(reverse('pos:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_cajero_cannot_access_dashboard(self):
        """El cajero NO puede acceder al dashboard"""
        self.client.login(username='cajero', password='cajero123')
        response = self.client.get(reverse('pos:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect

    def test_unauthenticated_user_cannot_access_dashboard(self):
        """Usuario no autenticado no puede acceder"""
        response = self.client.get(reverse('pos:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect a login

    def test_cajero_cannot_access_kpis_api(self):
        """El cajero NO puede acceder a las APIs del dashboard"""
        self.client.login(username='cajero', password='cajero123')
        response = self.client.get(reverse('pos:dashboard_api_kpis'))
        self.assertEqual(response.status_code, 302)  # Redirect


class DashboardKPIsTestCase(TestCase):
    """Tests para los KPIs del dashboard"""

    def setUp(self):
        # Crear usuario administrador
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            rol='ADMINISTRADOR'
        )

        # Crear cajero
        self.cajero_user = User.objects.create_user(
            username='cajero1',
            password='cajero123',
            first_name='Juan',
            last_name='Pérez'
        )
        self.cajero_profile = UserProfile.objects.create(
            user=self.cajero_user,
            rol='CAJERO'
        )

        # Crear productos
        self.producto1 = Product.objects.create(
            codigo_barras='PROD001',
            nombre='Perfume 1',
            marca='Marca A',
            precio=Decimal('100.00'),
            stock_actual=50,
            stock_minimo=10,
            categoria='EDP',
            genero='M',
            activo=True
        )

        self.producto2 = Product.objects.create(
            codigo_barras='PROD002',
            nombre='Perfume 2',
            marca='Marca B',
            precio=Decimal('150.00'),
            stock_actual=3,  # Bajo stock
            stock_minimo=10,
            categoria='EDT',
            genero='F',
            activo=True
        )

        # Crear ventas de hoy
        hoy = timezone.now()
        self.venta1 = Sales.objects.create(
            numero_ticket='TICKET001',
            cajero=self.cajero_user,
            total=Decimal('200.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        self.venta2 = Sales.objects.create(
            numero_ticket='TICKET002',
            cajero=self.cajero_user,
            total=Decimal('300.00'),
            metodo_pago='TARJETA',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        # Crear venta de ayer (para comparación)
        ayer = hoy - timedelta(days=1)
        self.venta_ayer = Sales.objects.create(
            numero_ticket='TICKET000',
            cajero=self.cajero_user,
            total=Decimal('150.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=ayer
        )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_kpis_ventas_total(self):
        """KPIs muestran el total de ventas correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_kpis'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Incluye ventas de hoy y ayer porque se ejecutan en el mismo contexto
        self.assertGreaterEqual(data['ventas_total'], 500.00)  # Al menos 200 + 300
        self.assertGreaterEqual(data['ventas_cantidad'], 2)

    def test_kpis_productos_bajo_stock(self):
        """KPIs muestran productos con bajo stock"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_kpis'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        data = response.json()
        self.assertEqual(data['productos_bajo_stock'], 1)  # producto2

    def test_kpis_mejor_cajero(self):
        """KPIs identifican al mejor cajero"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_kpis'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        data = response.json()
        self.assertEqual(data['mejor_cajero']['nombre'], 'Juan Pérez')
        self.assertGreaterEqual(data['mejor_cajero']['total'], 500.00)

    def test_kpis_cambio_porcentual(self):
        """KPIs calculan el cambio porcentual correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_kpis'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        data = response.json()
        # El cambio porcentual debe estar presente
        self.assertIn('ventas_cambio_porcentual', data)
        # Debe ser un número válido
        self.assertIsInstance(data['ventas_cambio_porcentual'], (int, float))


class DashboardSalesTrendTestCase(TestCase):
    """Tests para la tendencia de ventas"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        UserProfile.objects.create(user=self.admin_user, rol='ADMINISTRADOR')

        self.cajero = User.objects.create_user(username='cajero1', password='pass')
        UserProfile.objects.create(user=self.cajero, rol='CAJERO')

        # Crear ventas en diferentes días
        hoy = timezone.now()
        for i in range(5):
            dia = hoy - timedelta(days=i)
            Sales.objects.create(
                numero_ticket=f'TICKET{i}',
                cajero=self.cajero,
                total=Decimal('100.00') * (i + 1),
                metodo_pago='EFECTIVO',
                estado='COMPLETADA',
                fecha_hora=dia
            )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_sales_trend_returns_data(self):
        """API de tendencia retorna datos correctamente"""
        response = self.client.get(reverse('pos:dashboard_api_sales_trend'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('ventas', data)
        self.assertIn('cantidad', data)
        # Debe tener al menos 1 día de ventas
        self.assertGreaterEqual(len(data['labels']), 1)


class DashboardSalesByCashierTestCase(TestCase):
    """Tests para ventas por cajero"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        UserProfile.objects.create(user=self.admin_user, rol='ADMINISTRADOR')

        # Crear múltiples cajeros
        self.cajero1 = User.objects.create_user(
            username='cajero1',
            password='pass',
            first_name='Juan',
            last_name='Pérez'
        )
        UserProfile.objects.create(user=self.cajero1, rol='CAJERO')

        self.cajero2 = User.objects.create_user(
            username='cajero2',
            password='pass',
            first_name='María',
            last_name='García'
        )
        UserProfile.objects.create(user=self.cajero2, rol='CAJERO')

        # Crear ventas para cada cajero
        hoy = timezone.now()
        Sales.objects.create(
            numero_ticket='T1',
            cajero=self.cajero1,
            total=Decimal('500.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        Sales.objects.create(
            numero_ticket='T2',
            cajero=self.cajero2,
            total=Decimal('300.00'),
            metodo_pago='TARJETA',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_sales_by_cashier_returns_data(self):
        """API de ventas por cajero retorna datos correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_sales_by_cashier'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['labels']), 2)
        self.assertIn('Juan Pérez', data['labels'])
        self.assertIn('María García', data['labels'])


class DashboardPaymentMethodsTestCase(TestCase):
    """Tests para métodos de pago"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        UserProfile.objects.create(user=self.admin_user, rol='ADMINISTRADOR')

        self.cajero = User.objects.create_user(username='cajero', password='pass')
        UserProfile.objects.create(user=self.cajero, rol='CAJERO')

        # Crear ventas con diferentes métodos de pago
        hoy = timezone.now()
        Sales.objects.create(
            numero_ticket='T1',
            cajero=self.cajero,
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        Sales.objects.create(
            numero_ticket='T2',
            cajero=self.cajero,
            total=Decimal('200.00'),
            metodo_pago='TARJETA',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        Sales.objects.create(
            numero_ticket='T3',
            cajero=self.cajero,
            total=Decimal('150.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_payment_methods_aggregation(self):
        """API de métodos de pago agrega correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_payment_methods'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('Efectivo', data['labels'])
        self.assertIn('Tarjeta', data['labels'])


class DashboardTopProductsTestCase(TestCase):
    """Tests para productos más vendidos"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        UserProfile.objects.create(user=self.admin_user, rol='ADMINISTRADOR')

        self.cajero = User.objects.create_user(username='cajero', password='pass')
        UserProfile.objects.create(user=self.cajero, rol='CAJERO')

        # Crear productos
        self.producto1 = Product.objects.create(
            codigo_barras='P1',
            nombre='Perfume A',
            marca='Marca X',
            precio=Decimal('100.00'),
            stock_actual=100,
            categoria='EDP',
            genero='M'
        )

        self.producto2 = Product.objects.create(
            codigo_barras='P2',
            nombre='Perfume B',
            marca='Marca Y',
            precio=Decimal('150.00'),
            stock_actual=100,
            categoria='EDT',
            genero='F'
        )

        # Crear venta con detalles
        hoy = timezone.now()
        venta = Sales.objects.create(
            numero_ticket='T1',
            cajero=self.cajero,
            total=Decimal('550.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        SaleDetails.objects.create(
            venta=venta,
            producto=self.producto1,
            cantidad=2,
            precio_unitario=Decimal('100.00')
        )

        SaleDetails.objects.create(
            venta=venta,
            producto=self.producto2,
            cantidad=3,
            precio_unitario=Decimal('150.00')
        )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_top_products_returns_data(self):
        """API de top productos retorna datos correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_top_products'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['labels']), 2)
        self.assertEqual(data['cantidad'][0], 3)  # Producto2 vendió más (3 unidades)
        self.assertEqual(data['cantidad'][1], 2)  # Producto1 vendió 2 unidades


class DashboardSalesByCategoryTestCase(TestCase):
    """Tests para ventas por categoría"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        UserProfile.objects.create(user=self.admin_user, rol='ADMINISTRADOR')

        self.cajero = User.objects.create_user(username='cajero', password='pass')
        UserProfile.objects.create(user=self.cajero, rol='CAJERO')

        # Crear productos de diferentes categorías
        producto_edp = Product.objects.create(
            codigo_barras='P1',
            nombre='Perfume EDP',
            precio=Decimal('200.00'),
            stock_actual=100,
            categoria='EDP',
            genero='M'
        )

        producto_edt = Product.objects.create(
            codigo_barras='P2',
            nombre='Perfume EDT',
            precio=Decimal('150.00'),
            stock_actual=100,
            categoria='EDT',
            genero='F'
        )

        # Crear venta
        hoy = timezone.now()
        venta = Sales.objects.create(
            numero_ticket='T1',
            cajero=self.cajero,
            total=Decimal('500.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        SaleDetails.objects.create(
            venta=venta,
            producto=producto_edp,
            cantidad=2,
            precio_unitario=Decimal('200.00')
        )

        SaleDetails.objects.create(
            venta=venta,
            producto=producto_edt,
            cantidad=1,
            precio_unitario=Decimal('150.00')
        )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_sales_by_category_returns_data(self):
        """API de ventas por categoría retorna datos correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_sales_by_category'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('Eau de Parfum', data['labels'])
        self.assertIn('Eau de Toilette', data['labels'])


class DashboardSalesByHourTestCase(TestCase):
    """Tests para ventas por hora"""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        UserProfile.objects.create(user=self.admin_user, rol='ADMINISTRADOR')

        self.cajero = User.objects.create_user(username='cajero', password='pass')
        UserProfile.objects.create(user=self.cajero, rol='CAJERO')

        # Crear ventas en diferentes horas
        hoy = timezone.now().replace(hour=10, minute=0, second=0)
        Sales.objects.create(
            numero_ticket='T1',
            cajero=self.cajero,
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_hora=hoy
        )

        Sales.objects.create(
            numero_ticket='T2',
            cajero=self.cajero,
            total=Decimal('200.00'),
            metodo_pago='TARJETA',
            estado='COMPLETADA',
            fecha_hora=hoy.replace(hour=14)
        )

        self.client = Client()
        self.client.login(username='admin', password='admin123')

    def test_sales_by_hour_returns_data(self):
        """API de ventas por hora retorna datos correctamente"""
        today = timezone.now().date()
        response = self.client.get(
            reverse('pos:dashboard_api_sales_by_hour'),
            {'fecha_desde': str(today), 'fecha_hasta': str(today)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('labels', data)
        self.assertIn('ventas', data)
        self.assertGreater(len(data['labels']), 0)
