from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Product, Sales, SaleDetails, Inventory, UserProfile


class ProductModelTest(TestCase):
    """Pruebas unitarias para el modelo Product"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.producto = Product.objects.create(
            codigo_barras='TEST001',
            nombre='Perfume Test',
            marca='Marca Test',
            descripcion='Descripción de prueba',
            precio=Decimal('99.99'),
            stock_actual=10,
            stock_minimo=5,
            categoria='EDP',
            volumen=100,
            genero='U',
            activo=True
        )

    def test_crear_producto(self):
        """Prueba que se puede crear un producto correctamente"""
        self.assertEqual(self.producto.nombre, 'Perfume Test')
        self.assertEqual(self.producto.marca, 'Marca Test')
        self.assertEqual(self.producto.precio, Decimal('99.99'))
        self.assertEqual(self.producto.stock_actual, 10)
        self.assertEqual(self.producto.categoria, 'EDP')

    def test_producto_str_con_volumen(self):
        """Prueba el método __str__ cuando el producto tiene volumen"""
        expected = 'Perfume Test - Marca Test (100ml) [TEST001]'
        self.assertEqual(str(self.producto), expected)

    def test_producto_str_sin_volumen(self):
        """Prueba el método __str__ cuando el producto no tiene volumen"""
        producto_sin_volumen = Product.objects.create(
            codigo_barras='TEST002',
            nombre='Accesorio Test',
            marca='Marca Test',
            precio=Decimal('29.99'),
            stock_actual=5,
            categoria='ACCESORIO',
            volumen=None
        )
        expected = 'Accesorio Test - Marca Test [TEST002]'
        self.assertEqual(str(producto_sin_volumen), expected)

    def test_producto_disponible(self):
        """Prueba la propiedad 'disponible' cuando el producto está activo y tiene stock"""
        self.assertTrue(self.producto.disponible)

    def test_producto_no_disponible_sin_stock(self):
        """Prueba que un producto sin stock no está disponible"""
        self.producto.stock_actual = 0
        self.producto.save()
        self.assertFalse(self.producto.disponible)

    def test_producto_no_disponible_inactivo(self):
        """Prueba que un producto inactivo no está disponible"""
        self.producto.activo = False
        self.producto.save()
        self.assertFalse(self.producto.disponible)

    def test_requiere_reabastecimiento_true(self):
        """Prueba que un producto con stock <= stock_minimo requiere reabastecimiento"""
        self.producto.stock_actual = 5
        self.producto.stock_minimo = 5
        self.producto.save()
        self.assertTrue(self.producto.requiere_reabastecimiento)

    def test_requiere_reabastecimiento_false(self):
        """Prueba que un producto con stock > stock_minimo no requiere reabastecimiento"""
        self.producto.stock_actual = 10
        self.producto.stock_minimo = 5
        self.producto.save()
        self.assertFalse(self.producto.requiere_reabastecimiento)

    def test_valor_inventario(self):
        """Prueba el cálculo del valor total del inventario"""
        expected_value = Decimal('10') * Decimal('99.99')
        self.assertEqual(self.producto.valor_inventario, expected_value)

    def test_valor_inventario_sin_precio(self):
        """Prueba que el valor de inventario es 0 cuando el precio es None"""
        producto = Product.objects.create(
            codigo_barras='TEST003',
            nombre='Producto sin precio',
            marca='Test',
            precio=Decimal('0.01'),
            stock_actual=10,
            categoria='OTRO'
        )
        producto.precio = None
        self.assertEqual(producto.valor_inventario, Decimal('0.00'))

    def test_codigo_barras_unico(self):
        """Prueba que el código de barras debe ser único"""
        with self.assertRaises(Exception):
            Product.objects.create(
                codigo_barras='TEST001',  # Código duplicado
                nombre='Otro Producto',
                marca='Otra Marca',
                precio=Decimal('50.00'),
                stock_actual=5,
                categoria='EDT'
            )

    def test_precio_minimo_validacion(self):
        """Prueba que el precio no puede ser menor a 0.01"""
        producto = Product(
            codigo_barras='TEST004',
            nombre='Producto Precio Bajo',
            marca='Test',
            precio=Decimal('0.00'),
            stock_actual=5,
            categoria='EDT'
        )
        with self.assertRaises(ValidationError):
            producto.full_clean()

    def test_stock_negativo_validacion(self):
        """Prueba que el stock no puede ser negativo"""
        producto = Product(
            codigo_barras='TEST005',
            nombre='Producto Stock Negativo',
            marca='Test',
            precio=Decimal('50.00'),
            stock_actual=-5,
            categoria='EDT'
        )
        with self.assertRaises(ValidationError):
            producto.full_clean()


class SalesModelTest(TestCase):
    """Pruebas unitarias para el modelo Sales"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

        self.producto1 = Product.objects.create(
            codigo_barras='PROD001',
            nombre='Perfume 1',
            marca='Marca 1',
            precio=Decimal('100.00'),
            stock_actual=20,
            categoria='EDP'
        )

        self.producto2 = Product.objects.create(
            codigo_barras='PROD002',
            nombre='Perfume 2',
            marca='Marca 2',
            precio=Decimal('75.00'),
            stock_actual=15,
            categoria='EDT'
        )

    def test_crear_venta(self):
        """Prueba que se puede crear una venta correctamente"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario,
            descuento=Decimal('0.00')
        )
        self.assertEqual(venta.total, Decimal('100.00'))
        self.assertEqual(venta.metodo_pago, 'EFECTIVO')
        self.assertEqual(venta.cajero, self.usuario)
        self.assertEqual(venta.estado, 'COMPLETADA')

    def test_generacion_numero_ticket_automatico(self):
        """Prueba que el número de ticket se genera automáticamente"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        self.assertIsNotNone(venta.numero_ticket)
        self.assertTrue(venta.numero_ticket.startswith('2025'))

    def test_formato_numero_ticket(self):
        """Prueba que el formato del número de ticket es correcto (YYYYMMDD-NNNN)"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        partes = venta.numero_ticket.split('-')
        self.assertEqual(len(partes), 2)
        self.assertEqual(len(partes[0]), 8)  # YYYYMMDD
        self.assertEqual(len(partes[1]), 4)  # NNNN con padding

    def test_numero_ticket_incremental(self):
        """Prueba que los números de ticket son incrementales"""
        venta1 = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        venta2 = Sales.objects.create(
            total=Decimal('150.00'),
            metodo_pago='TARJETA',
            cajero=self.usuario
        )

        num1 = int(venta1.numero_ticket.split('-')[1])
        num2 = int(venta2.numero_ticket.split('-')[1])
        self.assertEqual(num2, num1 + 1)

    def test_venta_str(self):
        """Prueba el método __str__ de Sales"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        self.assertIn(venta.numero_ticket, str(venta))
        self.assertIn('$100.00', str(venta))

    def test_subtotal_sin_descuento(self):
        """Prueba el cálculo del subtotal sin descuento"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario,
            descuento=Decimal('0.00')
        )
        self.assertEqual(venta.subtotal, Decimal('100.00'))

    def test_subtotal_con_descuento(self):
        """Prueba el cálculo del subtotal con descuento"""
        venta = Sales.objects.create(
            total=Decimal('90.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario,
            descuento=Decimal('10.00')
        )
        self.assertEqual(venta.subtotal, Decimal('100.00'))

    def test_subtotal_sin_total(self):
        """Prueba que el subtotal es 0 cuando el total es None"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        venta.total = None
        self.assertEqual(venta.subtotal, Decimal('0.00'))

    def test_cantidad_productos_sin_detalles(self):
        """Prueba que cantidad_productos retorna 0 cuando no hay detalles"""
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        self.assertEqual(venta.cantidad_productos, 0)

    def test_cantidad_productos_con_detalles(self):
        """Prueba el cálculo de cantidad total de productos vendidos"""
        venta = Sales.objects.create(
            total=Decimal('250.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
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
            precio_unitario=Decimal('75.00')
        )

        self.assertEqual(venta.cantidad_productos, 5)

    def test_total_minimo_validacion(self):
        """Prueba que el total no puede ser negativo"""
        venta = Sales(
            total=Decimal('-10.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )
        with self.assertRaises(ValidationError):
            venta.full_clean()

    def test_descuento_negativo_validacion(self):
        """Prueba que el descuento no puede ser negativo"""
        venta = Sales(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario,
            descuento=Decimal('-10.00')
        )
        with self.assertRaises(ValidationError):
            venta.full_clean()


class SaleDetailsModelTest(TestCase):
    """Pruebas unitarias para el modelo SaleDetails"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.producto = Product.objects.create(
            codigo_barras='PROD001',
            nombre='Perfume Test',
            marca='Marca Test',
            precio=Decimal('100.00'),
            stock_actual=20,
            categoria='EDP'
        )

        self.venta = Sales.objects.create(
            total=Decimal('200.00'),
            metodo_pago='EFECTIVO',
            cajero=self.usuario
        )

    def test_crear_detalle_venta(self):
        """Prueba que se puede crear un detalle de venta correctamente"""
        detalle = SaleDetails.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=2,
            precio_unitario=Decimal('100.00')
        )
        self.assertEqual(detalle.cantidad, 2)
        self.assertEqual(detalle.precio_unitario, Decimal('100.00'))
        self.assertEqual(detalle.subtotal, Decimal('200.00'))

    def test_calculo_subtotal_automatico(self):
        """Prueba que el subtotal se calcula automáticamente"""
        detalle = SaleDetails.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=3,
            precio_unitario=Decimal('100.00')
        )
        self.assertEqual(detalle.subtotal, Decimal('300.00'))

    def test_calculo_subtotal_con_descuento(self):
        """Prueba el cálculo del subtotal con descuento aplicado"""
        detalle = SaleDetails.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=2,
            precio_unitario=Decimal('100.00'),
            descuento_aplicado=Decimal('20.00')
        )
        self.assertEqual(detalle.subtotal, Decimal('180.00'))

    def test_reduccion_stock_al_crear_detalle(self):
        """Prueba que el stock se reduce al crear un detalle de venta"""
        stock_inicial = self.producto.stock_actual
        SaleDetails.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=5,
            precio_unitario=Decimal('100.00')
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_inicial - 5)

    def test_error_stock_insuficiente(self):
        """Prueba que se lanza error cuando no hay stock suficiente"""
        self.producto.stock_actual = 2
        self.producto.save()

        with self.assertRaises(ValueError) as context:
            SaleDetails.objects.create(
                venta=self.venta,
                producto=self.producto,
                cantidad=5,
                precio_unitario=Decimal('100.00')
            )

        self.assertIn('Stock insuficiente', str(context.exception))

    def test_detalle_str(self):
        """Prueba el método __str__ de SaleDetails"""
        detalle = SaleDetails.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=2,
            precio_unitario=Decimal('100.00')
        )
        self.assertIn('2x', str(detalle))
        self.assertIn('Perfume Test', str(detalle))
        self.assertIn('$200.00', str(detalle))


class InventoryModelTest(TestCase):
    """Pruebas unitarias para el modelo Inventory"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.producto = Product.objects.create(
            codigo_barras='PROD001',
            nombre='Perfume Test',
            marca='Marca Test',
            precio=Decimal('100.00'),
            stock_actual=10,
            categoria='EDP'
        )

    def test_crear_movimiento_entrada(self):
        """Prueba crear un movimiento de entrada de inventario"""
        stock_inicial = self.producto.stock_actual
        movimiento = Inventory.objects.create(
            producto=self.producto,
            cantidad=5,
            tipo='ENTRADA',
            motivo='Compra a proveedor',
            usuario=self.usuario
        )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_inicial + 5)
        self.assertEqual(movimiento.stock_anterior, stock_inicial)
        self.assertEqual(movimiento.stock_nuevo, stock_inicial + 5)

    def test_crear_movimiento_salida(self):
        """Prueba crear un movimiento de salida de inventario"""
        stock_inicial = self.producto.stock_actual
        movimiento = Inventory.objects.create(
            producto=self.producto,
            cantidad=3,
            tipo='SALIDA',
            motivo='Producto dañado',
            usuario=self.usuario
        )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_inicial - 3)
        self.assertEqual(movimiento.stock_anterior, stock_inicial)
        self.assertEqual(movimiento.stock_nuevo, stock_inicial - 3)

    def test_error_stock_negativo(self):
        """Prueba que no se permite stock negativo"""
        self.producto.stock_actual = 2
        self.producto.save()

        with self.assertRaises(ValueError) as context:
            Inventory.objects.create(
                producto=self.producto,
                cantidad=5,
                tipo='SALIDA',
                motivo='Prueba stock negativo',
                usuario=self.usuario
            )

        self.assertIn('stock no puede ser negativo', str(context.exception))

    def test_movimiento_devolucion(self):
        """Prueba crear un movimiento de devolución"""
        stock_inicial = self.producto.stock_actual
        movimiento = Inventory.objects.create(
            producto=self.producto,
            cantidad=2,
            tipo='DEVOLUCION',
            motivo='Cliente devolvió producto',
            usuario=self.usuario
        )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_inicial + 2)


class UserProfileModelTest(TestCase):
    """Pruebas unitarias para el modelo UserProfile"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.usuario = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Juan',
            last_name='Pérez'
        )

    def test_crear_perfil_usuario(self):
        """Prueba que se puede crear un perfil de usuario"""
        perfil = UserProfile.objects.create(
            user=self.usuario,
            rol='CAJERO',
            turno='MATUTINO',
            activo=True
        )
        self.assertEqual(perfil.rol, 'CAJERO')
        self.assertEqual(perfil.turno, 'MATUTINO')
        self.assertTrue(perfil.activo)

    def test_perfil_str(self):
        """Prueba el método __str__ de UserProfile"""
        perfil = UserProfile.objects.create(
            user=self.usuario,
            rol='ADMINISTRADOR',
            turno='COMPLETO'
        )
        self.assertIn('Juan Pérez', str(perfil))
        self.assertIn('Administrador', str(perfil))

    def test_nombre_completo_property(self):
        """Prueba la propiedad nombre_completo"""
        perfil = UserProfile.objects.create(
            user=self.usuario,
            rol='CAJERO'
        )
        self.assertEqual(perfil.nombre_completo, 'Juan Pérez')

    def test_nombre_completo_sin_nombre(self):
        """Prueba nombre_completo cuando el usuario no tiene nombre"""
        usuario_sin_nombre = User.objects.create_user(
            username='sinombre',
            password='testpass123'
        )
        perfil = UserProfile.objects.create(
            user=usuario_sin_nombre,
            rol='CAJERO'
        )
        self.assertEqual(perfil.nombre_completo, 'sinombre')
