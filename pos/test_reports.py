"""
Pruebas unitarias para el sistema de reportes
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import datetime, timedelta
from .models import Product, Sales, SaleDetails
from .forms import SalesReportFilterForm, InventoryReportFilterForm
from .reports import (
    generate_sales_pdf,
    generate_sales_excel,
    generate_inventory_pdf,
    generate_inventory_excel
)

User = get_user_model()


class ReportFormsTestCase(TestCase):
    """Pruebas para los formularios de reportes"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cajero1',
            password='testpass123'
        )
        # Crear una venta para que el usuario aparezca en el queryset
        producto = Product.objects.create(
            nombre='Perfume Test',
            codigo_barras='TEST001',
            marca='Test Brand',
            categoria='EDP',
            genero='U',
            precio=Decimal('100.00'),
            stock_actual=10,
            stock_minimo=5
        )
        Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.user
        )

    def test_sales_report_filter_form_valid(self):
        """Prueba que el formulario de filtro de ventas acepta datos válidos"""
        form_data = {
            'fecha_desde': '2025-01-01',
            'fecha_hasta': '2025-12-31',
            'metodo_pago': 'EFECTIVO',
            'estado': 'COMPLETADA'
        }
        form = SalesReportFilterForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_sales_report_filter_form_empty(self):
        """Prueba que el formulario es válido sin datos (todos opcionales)"""
        form = SalesReportFilterForm(data={})
        self.assertTrue(form.is_valid())

    def test_sales_report_filter_form_cajero_queryset(self):
        """Prueba que el queryset de cajeros contiene solo usuarios con ventas"""
        form = SalesReportFilterForm()
        cajeros = form.fields['cajero'].queryset
        self.assertIn(self.user, cajeros)

    def test_inventory_report_filter_form_valid(self):
        """Prueba que el formulario de filtro de inventario acepta datos válidos"""
        form_data = {
            'categoria': 'EDP',
            'genero': 'U',
            'marca': 'Test',
            'solo_bajo_stock': True,
            'solo_activos': True
        }
        form = InventoryReportFilterForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_inventory_report_filter_form_empty(self):
        """Prueba que el formulario es válido sin datos"""
        form = InventoryReportFilterForm(data={})
        self.assertTrue(form.is_valid())


class SalesReportViewTestCase(TestCase):
    """Pruebas para la vista de reporte de ventas"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='cajero1',
            password='testpass123'
        )
        self.client.login(username='cajero1', password='testpass123')

        # Crear productos y ventas para pruebas
        self.producto1 = Product.objects.create(
            nombre='Perfume A',
            codigo_barras='PROD001',
            marca='Brand A',
            categoria='EDP',
            genero='M',
            precio=Decimal('150.00'),
            stock_actual=20,
            stock_minimo=5
        )

        self.venta1 = Sales.objects.create(
            total=Decimal('150.00'),
            metodo_pago='EFECTIVO',
            cajero=self.user,
            estado='COMPLETADA'
        )

        self.venta2 = Sales.objects.create(
            total=Decimal('300.00'),
            metodo_pago='TARJETA',
            cajero=self.user,
            estado='COMPLETADA',
            descuento=Decimal('50.00')
        )

    def test_sales_report_view_requires_login(self):
        """Prueba que la vista requiere autenticación"""
        self.client.logout()
        response = self.client.get(reverse('pos:sales_report'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))

    def test_sales_report_view_get(self):
        """Prueba que la vista de reporte de ventas se carga correctamente"""
        response = self.client.get(reverse('pos:sales_report'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/reports/sales_report.html')
        self.assertIn('form', response.context)
        self.assertIn('sales', response.context)
        self.assertIn('total_sales', response.context)
        self.assertIn('total_amount', response.context)

    def test_sales_report_view_totals(self):
        """Prueba que los totales se calculan correctamente"""
        response = self.client.get(reverse('pos:sales_report'))
        self.assertEqual(response.context['total_sales'], 2)
        self.assertEqual(response.context['total_amount'], Decimal('450.00'))

    def test_sales_report_filter_by_payment_method(self):
        """Prueba el filtrado por método de pago"""
        response = self.client.get(
            reverse('pos:sales_report'),
            {'metodo_pago': 'EFECTIVO'}
        )
        sales = response.context['sales']
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0].metodo_pago, 'EFECTIVO')

    def test_sales_report_filter_by_date(self):
        """Prueba el filtrado por fechas"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        response = self.client.get(
            reverse('pos:sales_report'),
            {
                'fecha_desde': yesterday.strftime('%Y-%m-%d'),
                'fecha_hasta': today.strftime('%Y-%m-%d')
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('sales', response.context)

    def test_sales_report_pdf_generation(self):
        """Prueba que se puede generar un PDF"""
        response = self.client.get(
            reverse('pos:sales_report'),
            {'format': 'pdf'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_sales_report_excel_generation(self):
        """Prueba que se puede generar un Excel"""
        response = self.client.get(
            reverse('pos:sales_report'),
            {'format': 'excel'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', response['Content-Disposition'])


class InventoryReportViewTestCase(TestCase):
    """Pruebas para la vista de reporte de inventario"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='cajero1',
            password='testpass123'
        )
        self.client.login(username='cajero1', password='testpass123')

        # Crear productos
        self.producto1 = Product.objects.create(
            nombre='Perfume A',
            codigo_barras='PROD001',
            marca='Brand A',
            categoria='EDP',
            genero='M',
            precio=Decimal('150.00'),
            stock_actual=20,
            stock_minimo=5,
            activo=True
        )

        self.producto2 = Product.objects.create(
            nombre='Colonia B',
            codigo_barras='PROD002',
            marca='Brand B',
            categoria='EDC',
            genero='F',
            precio=Decimal('80.00'),
            stock_actual=3,  # Bajo stock
            stock_minimo=10,
            activo=True
        )

        self.producto3 = Product.objects.create(
            nombre='Perfume C',
            codigo_barras='PROD003',
            marca='Brand C',
            categoria='EDP',
            genero='U',
            precio=Decimal('200.00'),
            stock_actual=15,
            stock_minimo=5,
            activo=False  # Inactivo
        )

    def test_inventory_report_view_requires_login(self):
        """Prueba que la vista requiere autenticación"""
        self.client.logout()
        response = self.client.get(reverse('pos:inventory_report'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))

    def test_inventory_report_view_get(self):
        """Prueba que la vista de reporte de inventario se carga correctamente"""
        response = self.client.get(reverse('pos:inventory_report'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/reports/inventory_report.html')
        self.assertIn('form', response.context)
        self.assertIn('products', response.context)
        self.assertIn('total_products', response.context)
        self.assertIn('low_stock_count', response.context)
        self.assertIn('total_value', response.context)

    def test_inventory_report_view_totals(self):
        """Prueba que los totales se calculan correctamente"""
        response = self.client.get(reverse('pos:inventory_report'))
        self.assertEqual(response.context['total_products'], 3)
        self.assertEqual(response.context['low_stock_count'], 1)

    def test_inventory_report_filter_by_category(self):
        """Prueba el filtrado por categoría"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'categoria': 'EDP'}
        )
        products = response.context['products']
        self.assertEqual(len(products), 2)
        for product in products:
            self.assertEqual(product.categoria, 'EDP')

    def test_inventory_report_filter_by_gender(self):
        """Prueba el filtrado por género"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'genero': 'M'}
        )
        products = response.context['products']
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].genero, 'M')

    def test_inventory_report_filter_by_brand(self):
        """Prueba el filtrado por marca"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'marca': 'Brand A'}
        )
        products = response.context['products']
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].marca, 'Brand A')

    def test_inventory_report_filter_low_stock(self):
        """Prueba el filtrado de productos con bajo stock"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'solo_bajo_stock': True}
        )
        products = response.context['products']
        self.assertEqual(len(products), 1)
        self.assertTrue(products[0].requiere_reabastecimiento)

    def test_inventory_report_filter_only_active(self):
        """Prueba el filtrado de solo productos activos"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'solo_activos': True}
        )
        products = response.context['products']
        self.assertEqual(len(products), 2)
        for product in products:
            self.assertTrue(product.activo)

    def test_inventory_report_pdf_generation(self):
        """Prueba que se puede generar un PDF"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'format': 'pdf'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_inventory_report_excel_generation(self):
        """Prueba que se puede generar un Excel"""
        response = self.client.get(
            reverse('pos:inventory_report'),
            {'format': 'excel'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', response['Content-Disposition'])


class ReportUtilitiesTestCase(TestCase):
    """Pruebas para las funciones de utilidades de reportes"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cajero1',
            password='testpass123'
        )

        self.producto = Product.objects.create(
            nombre='Perfume Test',
            codigo_barras='TEST001',
            marca='Test Brand',
            categoria='EDP',
            genero='U',
            precio=Decimal('100.00'),
            stock_actual=10,
            stock_minimo=5
        )

        self.venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.user
        )

    def test_generate_sales_pdf_returns_response(self):
        """Prueba que generate_sales_pdf retorna una respuesta HTTP"""
        sales = Sales.objects.all()
        response = generate_sales_pdf(sales)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_generate_sales_excel_returns_response(self):
        """Prueba que generate_sales_excel retorna una respuesta HTTP"""
        sales = Sales.objects.all()
        response = generate_sales_excel(sales)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', response['Content-Disposition'])

    def test_generate_inventory_pdf_returns_response(self):
        """Prueba que generate_inventory_pdf retorna una respuesta HTTP"""
        products = Product.objects.all()
        response = generate_inventory_pdf(products)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_generate_inventory_excel_returns_response(self):
        """Prueba que generate_inventory_excel retorna una respuesta HTTP"""
        products = Product.objects.all()
        response = generate_inventory_excel(products)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', response['Content-Disposition'])

    def test_generate_sales_pdf_with_custom_filename(self):
        """Prueba que se puede especificar un nombre de archivo personalizado"""
        sales = Sales.objects.all()
        response = generate_sales_pdf(sales, filename='custom_report.pdf')
        self.assertIn('custom_report.pdf', response['Content-Disposition'])

    def test_generate_inventory_excel_with_custom_filename(self):
        """Prueba que se puede especificar un nombre de archivo personalizado"""
        products = Product.objects.all()
        response = generate_inventory_excel(products, filename='custom_inventory.xlsx')
        self.assertIn('custom_inventory.xlsx', response['Content-Disposition'])
