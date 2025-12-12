from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.models import User
from unittest import skipIf
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from decimal import Decimal
from .models import Product, Sales, UserProfile
import time
import shutil


# Verificar si Chrome está disponible
CHROME_AVAILABLE = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')


@skipIf(not CHROME_AVAILABLE, "Chrome/Chromium no está instalado. Instala Chrome o Chromium para ejecutar estas pruebas.")
class AdminSeleniumTests(StaticLiveServerTestCase):
    """
    Pruebas de integración con Selenium para el panel de administración de Django.
    Estas pruebas verifican la funcionalidad del sistema POS a través del admin.

    NOTA: Estas pruebas requieren que Chrome o Chromium esté instalado en el sistema.
    Si Chrome no está disponible, estas pruebas se saltarán automáticamente.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Configurar opciones de Chrome para ejecución headless
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        # Inicializar el driver de Chrome
        try:
            service = Service(ChromeDriverManager().install())
            cls.selenium = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"Error al inicializar Chrome: {e}")
            raise

        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        """Crear usuario administrador para las pruebas"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )

    def test_admin_login(self):
        """Prueba que se puede acceder al panel de administración"""
        self.selenium.get(f'{self.live_server_url}/admin/')

        # Esperar a que cargue la página de login
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )

        password_input = self.selenium.find_element(By.NAME, "password")

        # Llenar formulario de login
        username_input.send_keys('admin')
        password_input.send_keys('adminpass123')

        # Hacer click en el botón de login
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

        # Verificar que se redirigió al admin
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "site-name"))
        )

        self.assertIn('Django administration', self.selenium.page_source)

    def test_admin_create_product(self):
        """Prueba que se puede crear un producto desde el admin"""
        # Login
        self.selenium.get(f'{self.live_server_url}/admin/')
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.send_keys('admin')
        password_input = self.selenium.find_element(By.NAME, "password")
        password_input.send_keys('adminpass123')
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

        # Navegar a la lista de productos
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "site-name"))
        )

        # Buscar el link de Products en el admin
        try:
            products_link = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Products"))
            )
            products_link.click()
        except:
            # Si no encuentra por texto, buscar en la estructura del admin
            self.selenium.get(f'{self.live_server_url}/admin/pos/product/')

        # Click en "Add product"
        add_button = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Add product"))
        )
        add_button.click()

        # Llenar formulario de producto
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "codigo_barras"))
        )

        self.selenium.find_element(By.NAME, "codigo_barras").send_keys('SELENIUM001')
        self.selenium.find_element(By.NAME, "nombre").send_keys('Producto Selenium Test')
        self.selenium.find_element(By.NAME, "marca").send_keys('Marca Test')
        self.selenium.find_element(By.NAME, "precio").send_keys('99.99')
        self.selenium.find_element(By.NAME, "stock_actual").send_keys('10')
        self.selenium.find_element(By.NAME, "stock_minimo").send_keys('5')

        # Seleccionar categoría
        categoria_select = self.selenium.find_element(By.NAME, "categoria")
        for option in categoria_select.find_elements(By.TAG_NAME, 'option'):
            if option.get_attribute('value') == 'EDP':
                option.click()
                break

        # Guardar
        save_button = self.selenium.find_element(By.NAME, "_save")
        save_button.click()

        # Verificar que se creó el producto
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "success"))
        )

        # Verificar en la base de datos
        product = Product.objects.get(codigo_barras='SELENIUM001')
        self.assertEqual(product.nombre, 'Producto Selenium Test')
        self.assertEqual(product.precio, Decimal('99.99'))

    def test_admin_view_products_list(self):
        """Prueba que se puede ver la lista de productos en el admin"""
        # Crear algunos productos de prueba
        Product.objects.create(
            codigo_barras='TEST001',
            nombre='Producto 1',
            marca='Marca 1',
            precio=Decimal('100.00'),
            stock_actual=10,
            categoria='EDP'
        )
        Product.objects.create(
            codigo_barras='TEST002',
            nombre='Producto 2',
            marca='Marca 2',
            precio=Decimal('75.00'),
            stock_actual=5,
            categoria='EDT'
        )

        # Login
        self.selenium.get(f'{self.live_server_url}/admin/')
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.send_keys('admin')
        password_input = self.selenium.find_element(By.NAME, "password")
        password_input.send_keys('adminpass123')
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

        # Ir a la lista de productos
        self.selenium.get(f'{self.live_server_url}/admin/pos/product/')

        # Verificar que los productos aparecen
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "result_list"))
        )

        page_source = self.selenium.page_source
        self.assertIn('Producto 1', page_source)
        self.assertIn('Producto 2', page_source)

    def test_admin_search_product(self):
        """Prueba la funcionalidad de búsqueda de productos en el admin"""
        # Crear producto de prueba
        Product.objects.create(
            codigo_barras='SEARCH001',
            nombre='Producto Buscable',
            marca='Marca Especial',
            precio=Decimal('150.00'),
            stock_actual=20,
            categoria='PARFUM'
        )

        # Login
        self.selenium.get(f'{self.live_server_url}/admin/')
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.send_keys('admin')
        password_input = self.selenium.find_element(By.NAME, "password")
        password_input.send_keys('adminpass123')
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

        # Ir a la lista de productos
        self.selenium.get(f'{self.live_server_url}/admin/pos/product/')

        # Buscar el producto
        search_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "searchbar"))
        )
        search_input.send_keys('Buscable')
        search_input.submit()

        # Verificar que aparece el resultado
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "result_list"))
        )

        self.assertIn('Producto Buscable', self.selenium.page_source)

    def test_admin_create_sale(self):
        """Prueba que se puede crear una venta desde el admin"""
        # Crear producto y usuario cajero
        producto = Product.objects.create(
            codigo_barras='SALE001',
            nombre='Producto Venta',
            marca='Marca Venta',
            precio=Decimal('100.00'),
            stock_actual=10,
            categoria='EDP'
        )

        # Login
        self.selenium.get(f'{self.live_server_url}/admin/')
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.send_keys('admin')
        password_input = self.selenium.find_element(By.NAME, "password")
        password_input.send_keys('adminpass123')
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

        # Ir a crear venta
        self.selenium.get(f'{self.live_server_url}/admin/pos/sales/add/')

        # Llenar formulario de venta
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "total"))
        )

        self.selenium.find_element(By.NAME, "total").send_keys('100.00')

        # Seleccionar método de pago
        metodo_pago_select = self.selenium.find_element(By.NAME, "metodo_pago")
        for option in metodo_pago_select.find_elements(By.TAG_NAME, 'option'):
            if option.get_attribute('value') == 'EFECTIVO':
                option.click()
                break

        # Seleccionar cajero
        cajero_select = self.selenium.find_element(By.NAME, "cajero")
        for option in cajero_select.find_elements(By.TAG_NAME, 'option'):
            if option.get_attribute('value') == str(self.admin_user.id):
                option.click()
                break

        # Guardar
        save_button = self.selenium.find_element(By.NAME, "_save")
        save_button.click()

        # Verificar que se creó la venta
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "success"))
        )

        # Verificar en la base de datos
        self.assertTrue(Sales.objects.filter(total=Decimal('100.00')).exists())


@skipIf(not CHROME_AVAILABLE, "Chrome/Chromium no está instalado. Instala Chrome o Chromium para ejecutar estas pruebas.")
class ProductWorkflowSeleniumTests(StaticLiveServerTestCase):
    """
    Pruebas de flujo de trabajo completo para gestión de productos.

    NOTA: Estas pruebas requieren que Chrome o Chromium esté instalado en el sistema.
    Si Chrome no está disponible, estas pruebas se saltarán automáticamente.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        try:
            service = Service(ChromeDriverManager().install())
            cls.selenium = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"Error al inicializar Chrome: {e}")
            raise

        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )

    def test_full_product_lifecycle(self):
        """
        Prueba el ciclo de vida completo de un producto:
        1. Crear producto
        2. Editar producto
        3. Verificar cambios
        """
        # Login
        self.selenium.get(f'{self.live_server_url}/admin/')
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.send_keys('admin')
        password_input = self.selenium.find_element(By.NAME, "password")
        password_input.send_keys('adminpass123')
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

        # Crear producto
        self.selenium.get(f'{self.live_server_url}/admin/pos/product/add/')

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "codigo_barras"))
        )

        self.selenium.find_element(By.NAME, "codigo_barras").send_keys('LIFECYCLE001')
        self.selenium.find_element(By.NAME, "nombre").send_keys('Producto Inicial')
        self.selenium.find_element(By.NAME, "marca").send_keys('Marca Inicial')
        self.selenium.find_element(By.NAME, "precio").send_keys('50.00')
        self.selenium.find_element(By.NAME, "stock_actual").send_keys('5')

        categoria_select = self.selenium.find_element(By.NAME, "categoria")
        for option in categoria_select.find_elements(By.TAG_NAME, 'option'):
            if option.get_attribute('value') == 'EDT':
                option.click()
                break

        save_button = self.selenium.find_element(By.NAME, "_save")
        save_button.click()

        # Verificar creación
        product = Product.objects.get(codigo_barras='LIFECYCLE001')
        self.assertEqual(product.nombre, 'Producto Inicial')
        self.assertEqual(product.precio, Decimal('50.00'))

        # Editar producto
        self.selenium.get(f'{self.live_server_url}/admin/pos/product/{product.id}/change/')

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "nombre"))
        )

        nombre_input = self.selenium.find_element(By.NAME, "nombre")
        nombre_input.clear()
        nombre_input.send_keys('Producto Actualizado')

        precio_input = self.selenium.find_element(By.NAME, "precio")
        precio_input.clear()
        precio_input.send_keys('75.00')

        save_button = self.selenium.find_element(By.NAME, "_save")
        save_button.click()

        # Verificar actualización
        product.refresh_from_db()
        self.assertEqual(product.nombre, 'Producto Actualizado')
        self.assertEqual(product.precio, Decimal('75.00'))


@skipIf(not CHROME_AVAILABLE, "Chrome/Chromium no está instalado. Instala Chrome o Chromium para ejecutar estas pruebas.")
class POSWorkflowSeleniumTests(StaticLiveServerTestCase):
    """
    Pruebas de integración con Selenium para el flujo completo del POS.
    Simula el proceso completo de una venta desde la caja registradora.
    
    NOTA: Estas pruebas requieren que Chrome o Chromium esté instalado en el sistema.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        try:
            service = Service(ChromeDriverManager().install())
            cls.selenium = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"Error al inicializar Chrome: {e}")
            raise

        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        """Crear usuario y productos de prueba"""
        self.user = User.objects.create_user(
            username='cajero',
            password='cajero123',
            first_name='Test',
            last_name='Cajero'
        )

        self.product1 = Product.objects.create(
            codigo_barras='POS001',
            nombre='Perfume Selenium 1',
            marca='Marca Selenium',
            precio=Decimal('100.00'),
            stock_actual=20,
            categoria='EDP',
            activo=True
        )

        self.product2 = Product.objects.create(
            codigo_barras='POS002',
            nombre='Perfume Selenium 2',
            marca='Marca Selenium',
            precio=Decimal('75.00'),
            stock_actual=15,
            categoria='EDT',
            activo=True
        )

    def login(self):
        """Helper para hacer login"""
        self.selenium.get(f'{self.live_server_url}/login/')
        
        username_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        password_input = self.selenium.find_element(By.NAME, "password")
        
        username_input.send_keys('cajero')
        password_input.send_keys('cajero123')
        
        login_button = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]')
        login_button.click()

    def test_pos_access_requires_login(self):
        """Prueba que el POS requiere login"""
        self.selenium.get(f'{self.live_server_url}/pos/')
        
        # Debe redirigir a login
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        self.assertIn('/login/', self.selenium.current_url)

    def test_complete_sale_workflow(self):
        """Prueba el flujo completo de una venta"""
        # Login
        self.login()

        # Ir al POS
        self.selenium.get(f'{self.live_server_url}/pos/')

        # Verificar que estamos en el POS
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h2"))
        )
        self.assertIn('Caja Registradora', self.selenium.page_source)

        # Buscar producto
        search_input = self.selenium.find_element(By.NAME, "search")
        search_input.send_keys('POS001')
        
        search_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        search_button.click()

        # Esperar resultados de búsqueda
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Verificar que aparece el producto
        self.assertIn('Perfume Selenium 1', self.selenium.page_source)

        # Agregar al carrito
        cantidad_input = self.selenium.find_element(By.CSS_SELECTOR, 'input[name="cantidad"]')
        cantidad_input.clear()
        cantidad_input.send_keys('2')

        add_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        add_button.click()

        # Esperar redirección al POS
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h3"))
        )

        # Verificar que el producto está en el carrito
        self.assertIn('Perfume Selenium 1', self.selenium.page_source)
        self.assertIn('200.00', self.selenium.page_source)  # 2 x 100

        # Proceder al checkout
        checkout_link = self.selenium.find_element(By.LINK_TEXT, 'Proceder al Pago')
        checkout_link.click()

        # Esperar página de checkout
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "form"))
        )

        # Seleccionar método de pago
        efectivo_radio = self.selenium.find_element(By.CSS_SELECTOR, 'input[value="EFECTIVO"]')
        efectivo_radio.click()

        # Completar venta
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_button.click()

        # Esperar página de detalle de venta
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h2"))
        )

        # Verificar que la venta se completó
        self.assertIn('Detalle de Venta', self.selenium.page_source)
        self.assertIn('Perfume Selenium 1', self.selenium.page_source)

        # Verificar que la venta se creó en la base de datos
        self.assertEqual(Sales.objects.count(), 1)
        venta = Sales.objects.first()
        self.assertEqual(venta.total, Decimal('200.00'))
        self.assertEqual(venta.cajero, self.user)

        # Verificar que el stock se redujo
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_actual, 18)  # 20 - 2

    def test_add_multiple_products_to_cart(self):
        """Prueba agregar múltiples productos al carrito"""
        self.login()
        self.selenium.get(f'{self.live_server_url}/pos/')

        # Ir a lista de productos
        products_link = self.selenium.find_element(By.LINK_TEXT, 'Ver todos los productos')
        products_link.click()

        # Esperar que cargue la lista
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Agregar primer producto
        cantidad_inputs = self.selenium.find_elements(By.CSS_SELECTOR, 'input[name="cantidad"]')
        cantidad_inputs[0].clear()
        cantidad_inputs[0].send_keys('2')

        add_buttons = self.selenium.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
        add_buttons[0].click()

        # Esperar mensaje de éxito
        time.sleep(1)

        # Volver a productos
        self.selenium.get(f'{self.live_server_url}/pos/products/')

        # Agregar segundo producto
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        cantidad_inputs = self.selenium.find_elements(By.CSS_SELECTOR, 'input[name="cantidad"]')
        cantidad_inputs[1].clear()
        cantidad_inputs[1].send_keys('3')

        add_buttons = self.selenium.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
        add_buttons[1].click()

        # Ir a la caja
        self.selenium.get(f'{self.live_server_url}/pos/')

        # Verificar que ambos productos están en el carrito
        self.assertIn('Perfume Selenium 1', self.selenium.page_source)
        self.assertIn('Perfume Selenium 2', self.selenium.page_source)

    def test_update_cart_quantity(self):
        """Prueba actualizar la cantidad de un producto en el carrito"""
        self.login()
        self.selenium.get(f'{self.live_server_url}/pos/products/')

        # Agregar producto al carrito
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        add_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        add_button.click()

        # Ir a la caja
        self.selenium.get(f'{self.live_server_url}/pos/')

        # Actualizar cantidad
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        cantidad_input = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="number"]')
        cantidad_input.clear()
        cantidad_input.send_keys('5')

        update_button = self.selenium.find_element(By.XPATH, '//button[text()="Actualizar"]')
        update_button.click()

        # Esperar mensaje de éxito
        time.sleep(1)

        # Verificar que la cantidad se actualizó
        cantidad_input = self.selenium.find_element(By.CSS_SELECTOR, 'input[type="number"]')
        self.assertEqual(cantidad_input.get_attribute('value'), '5')

    def test_remove_product_from_cart(self):
        """Prueba eliminar un producto del carrito"""
        self.login()
        self.selenium.get(f'{self.live_server_url}/pos/products/')

        # Agregar producto al carrito
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        add_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        add_button.click()

        # Ir a la caja
        self.selenium.get(f'{self.live_server_url}/pos/')

        # Verificar que el producto está en el carrito
        self.assertIn('Perfume Selenium 1', self.selenium.page_source)

        # Eliminar producto
        remove_button = self.selenium.find_element(By.XPATH, '//button[text()="Eliminar"]')
        remove_button.click()

        # Esperar mensaje
        time.sleep(1)

        # Verificar que el carrito está vacío
        self.assertIn('vacío', self.selenium.page_source)

    def test_view_sales_list(self):
        """Prueba ver la lista de ventas"""
        # Crear una venta de prueba
        venta = Sales.objects.create(
            total=Decimal('100.00'),
            metodo_pago='EFECTIVO',
            cajero=self.user
        )

        self.login()
        self.selenium.get(f'{self.live_server_url}/pos/sales/')

        # Verificar que la venta aparece
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        self.assertIn(venta.numero_ticket, self.selenium.page_source)
        self.assertIn('100.00', self.selenium.page_source)

    def test_view_sale_detail(self):
        """Prueba ver el detalle de una venta"""
        from .models import SaleDetails

        # Crear una venta con detalles
        venta = Sales.objects.create(
            total=Decimal('200.00'),
            metodo_pago='TARJETA',
            cajero=self.user
        )
        SaleDetails.objects.create(
            venta=venta,
            producto=self.product1,
            cantidad=2,
            precio_unitario=self.product1.precio
        )

        self.login()
        self.selenium.get(f'{self.live_server_url}/pos/sales/{venta.pk}/')

        # Verificar información de la venta
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h2"))
        )

        self.assertIn(venta.numero_ticket, self.selenium.page_source)
        self.assertIn('Perfume Selenium 1', self.selenium.page_source)
        self.assertIn('200.00', self.selenium.page_source)
        self.assertIn('TARJETA', self.selenium.page_source)
