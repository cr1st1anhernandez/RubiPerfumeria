from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Product, Sales, SaleDetails
from .forms import ProductSearchForm, CompleteSaleForm, ProductFilterForm


class FormsTestCase(TestCase):
    """Pruebas unitarias para los formularios del POS"""

    def test_product_search_form_valid(self):
        """Prueba que el formulario de búsqueda acepta datos válidos"""
        form = ProductSearchForm(data={'search': 'perfume'})
        self.assertTrue(form.is_valid())

    def test_product_search_form_empty(self):
        """Prueba que el formulario acepta búsqueda vacía"""
        form = ProductSearchForm(data={'search': ''})
        self.assertTrue(form.is_valid())

    def test_complete_sale_form_valid(self):
        """Prueba que el formulario de venta acepta datos válidos"""
        form = CompleteSaleForm(data={
            'metodo_pago': 'EFECTIVO',
            'descuento': Decimal('0.00'),
            'notas': 'Test'
        })
        self.assertTrue(form.is_valid())

    def test_complete_sale_form_with_discount(self):
        """Prueba que el formulario acepta descuentos"""
        form = CompleteSaleForm(data={
            'metodo_pago': 'TARJETA',
            'descuento': Decimal('10.00'),
            'notas': ''
        })
        self.assertTrue(form.is_valid())

    def test_product_filter_form_all_filters(self):
        """Prueba el formulario de filtros con todos los campos"""
        form = ProductFilterForm(data={
            'categoria': 'EDP',
            'genero': 'M',
            'solo_disponibles': True,
            'bajo_stock': False
        })
        self.assertTrue(form.is_valid())


class POSViewsTestCase(TestCase):
    """Pruebas unitarias para las vistas del POS"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testcajero',
            password='testpass123'
        )

        self.product1 = Product.objects.create(
            codigo_barras='TEST001',
            nombre='Perfume Test 1',
            marca='Marca Test',
            precio=Decimal('100.00'),
            stock_actual=10,
            categoria='EDP'
        )

        self.product2 = Product.objects.create(
            codigo_barras='TEST002',
            nombre='Perfume Test 2',
            marca='Marca Test',
            precio=Decimal('75.00'),
            stock_actual=5,
            categoria='EDT'
        )

    def test_pos_index_requires_login(self):
        """Prueba que la vista principal requiere login"""
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_pos_index_authenticated(self):
        """Prueba que un usuario autenticado puede acceder al POS"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/index.html')

    def test_pos_index_empty_cart(self):
        """Prueba que el carrito inicia vacío"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.context['cart_count'], 0)
        self.assertEqual(response.context['subtotal'], Decimal('0.00'))

    def test_search_product_view(self):
        """Prueba la búsqueda de productos"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:search_product'), {'search': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfume Test 1')
        self.assertContains(response, 'Perfume Test 2')

    def test_search_product_by_barcode(self):
        """Prueba la búsqueda por código de barras"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:search_product'), {'search': 'TEST001'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfume Test 1')
        self.assertNotContains(response, 'Perfume Test 2')

    def test_add_to_cart(self):
        """Prueba agregar un producto al carrito"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.post(
            reverse('pos:add_to_cart', args=[self.product1.id]),
            {'cantidad': 2}
        )
        self.assertEqual(response.status_code, 302)

        # Verificar que el carrito tiene el producto
        session = self.client.session
        cart = session.get('cart', {})
        self.assertIn(str(self.product1.id), cart)
        self.assertEqual(cart[str(self.product1.id)]['cantidad'], 2)

    def test_add_to_cart_insufficient_stock(self):
        """Prueba agregar más productos de los disponibles"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.post(
            reverse('pos:add_to_cart', args=[self.product1.id]),
            {'cantidad': 20}  # Solo hay 10 en stock
        )

        # Debe redirigir con mensaje de error
        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any('insuficiente' in str(m).lower() for m in messages))

    def test_remove_from_cart(self):
        """Prueba eliminar un producto del carrito"""
        self.client.login(username='testcajero', password='testpass123')

        # Agregar producto al carrito
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {'cantidad': 2, 'precio': str(self.product1.precio)}
        }
        session.save()

        # Eliminar producto
        response = self.client.post(reverse('pos:remove_from_cart', args=[self.product1.id]))
        self.assertEqual(response.status_code, 302)

        # Verificar que el carrito está vacío
        session = self.client.session
        cart = session.get('cart', {})
        self.assertNotIn(str(self.product1.id), cart)

    def test_update_cart_quantity(self):
        """Prueba actualizar la cantidad de un producto en el carrito"""
        self.client.login(username='testcajero', password='testpass123')

        # Agregar producto al carrito
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {'cantidad': 2, 'precio': str(self.product1.precio)}
        }
        session.save()

        # Actualizar cantidad
        response = self.client.post(
            reverse('pos:update_cart_quantity', args=[self.product1.id]),
            {'cantidad': 5}
        )
        self.assertEqual(response.status_code, 302)

        # Verificar nueva cantidad
        session = self.client.session
        cart = session.get('cart', {})
        self.assertEqual(cart[str(self.product1.id)]['cantidad'], 5)

    def test_clear_cart(self):
        """Prueba vaciar el carrito"""
        self.client.login(username='testcajero', password='testpass123')

        # Agregar productos al carrito
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {'cantidad': 2, 'precio': str(self.product1.precio)},
            str(self.product2.id): {'cantidad': 1, 'precio': str(self.product2.precio)}
        }
        session.save()

        # Vaciar carrito
        response = self.client.get(reverse('pos:clear_cart'))
        self.assertEqual(response.status_code, 302)

        # Verificar que el carrito está vacío
        session = self.client.session
        cart = session.get('cart', {})
        self.assertEqual(len(cart), 0)

    def test_checkout_empty_cart(self):
        """Prueba que no se puede hacer checkout con carrito vacío"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:checkout'))
        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any('vacío' in str(m).lower() for m in messages))

    def test_checkout_view(self):
        """Prueba la vista de checkout"""
        self.client.login(username='testcajero', password='testpass123')

        # Agregar productos al carrito
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {'cantidad': 2, 'precio': str(self.product1.precio)}
        }
        session.save()

        response = self.client.get(reverse('pos:checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/checkout.html')
        self.assertIn('form', response.context)
        self.assertIn('cart_items', response.context)

    def test_complete_sale(self):
        """Prueba completar una venta"""
        self.client.login(username='testcajero', password='testpass123')

        # Agregar productos al carrito
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {'cantidad': 2, 'precio': str(self.product1.precio)}
        }
        session.save()

        # Stock inicial
        stock_inicial = self.product1.stock_actual

        # Completar venta
        response = self.client.post(reverse('pos:checkout'), {
            'metodo_pago': 'EFECTIVO',
            'descuento': Decimal('0.00'),
            'notas': 'Venta de prueba'
        })

        # Verificar redirección
        self.assertEqual(response.status_code, 302)

        # Verificar que se creó la venta
        self.assertEqual(Sales.objects.count(), 1)
        venta = Sales.objects.first()
        self.assertEqual(venta.total, Decimal('200.00'))
        self.assertEqual(venta.cajero, self.user)
        self.assertEqual(venta.metodo_pago, 'EFECTIVO')

        # Verificar detalles de venta
        self.assertEqual(venta.detalles.count(), 1)
        detalle = venta.detalles.first()
        self.assertEqual(detalle.producto, self.product1)
        self.assertEqual(detalle.cantidad, 2)

        # Verificar que el stock se redujo
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_actual, stock_inicial - 2)

        # Verificar que el carrito se vació
        session = self.client.session
        cart = session.get('cart', {})
        self.assertEqual(len(cart), 0)

    def test_product_list_view(self):
        """Prueba la vista de lista de productos"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/product_list.html')
        self.assertContains(response, 'Perfume Test 1')
        self.assertContains(response, 'Perfume Test 2')

    def test_product_list_filter_by_category(self):
        """Prueba filtrar productos por categoría"""
        self.client.login(username='testcajero', password='testpass123')
        response = self.client.get(reverse('pos:product_list'), {'categoria': 'EDP'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfume Test 1')
        self.assertNotContains(response, 'Perfume Test 2')

    def test_sale_list_view(self):
        """Prueba la vista de lista de ventas"""
        self.client.login(username='testcajero', password='testpass123')

        # Crear una venta
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.user
        )

        response = self.client.get(reverse('pos:sale_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/sale_list.html')
        self.assertContains(response, venta.numero_ticket)

    def test_sale_detail_view(self):
        """Prueba la vista de detalle de venta"""
        self.client.login(username='testcajero', password='testpass123')

        # Crear una venta con detalles
        venta = Sales.objects.create(
            total=Decimal('200.00'),
            metodo_pago='EFECTIVO',
            cajero=self.user
        )
        SaleDetails.objects.create(
            venta=venta,
            producto=self.product1,
            cantidad=2,
            precio_unitario=self.product1.precio
        )

        response = self.client.get(reverse('pos:sale_detail', args=[venta.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pos/sale_detail.html')
        self.assertContains(response, venta.numero_ticket)
        self.assertContains(response, self.product1.nombre)

    def test_sale_with_discount(self):
        """Prueba crear una venta con descuento"""
        self.client.login(username='testcajero', password='testpass123')

        # Agregar productos al carrito
        session = self.client.session
        session['cart'] = {
            str(self.product1.id): {'cantidad': 2, 'precio': str(self.product1.precio)}
        }
        session.save()

        # Completar venta con descuento
        response = self.client.post(reverse('pos:checkout'), {
            'metodo_pago': 'TARJETA',
            'descuento': Decimal('20.00'),
            'notas': ''
        })

        # Verificar que se aplicó el descuento
        venta = Sales.objects.first()
        self.assertEqual(venta.total, Decimal('180.00'))  # 200 - 20
        self.assertEqual(venta.descuento, Decimal('20.00'))
        self.assertEqual(venta.subtotal, Decimal('200.00'))
