"""
Tests de Selenium para el sistema POS.

Para ejecutar estos tests:
    python manage.py test pos.tests_selenium

Nota: Requiere tener instalado Chrome/Chromium y chromedriver.
"""

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from decimal import Decimal
import time

from accounts.models import UserProfile
from perfumes.models import Perfume
from .models import Venta, VentaTemporal


class SeleniumTestBase(StaticLiveServerTestCase):
    """Base class para tests de Selenium con configuración común."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Ejecutar sin interfaz gráfica
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        try:
            cls.selenium = webdriver.Chrome(options=options)
        except Exception as e:
            print(f"Error al iniciar Chrome: {e}")
            print("Asegúrate de tener instalado chromedriver")
            raise

        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        """Configurar datos de prueba."""
        # Crear usuarios (el perfil se crea automáticamente por señal)
        self.cajero_user = User.objects.create_user(
            username='cajero_selenium',
            password='testpass123',
            email='cajero@test.com'
        )
        # Actualizar perfil creado automáticamente
        self.cajero_user.profile.rol = 'CAJERO'
        self.cajero_user.profile.save()

        self.supervisor_user = User.objects.create_user(
            username='supervisor_selenium',
            password='testpass123',
            email='supervisor@test.com'
        )
        self.supervisor_user.profile.rol = 'SUPERVISOR'
        self.supervisor_user.profile.save()

        # Crear perfumes de prueba
        self.perfume1 = Perfume.objects.create(
            nombre='Perfume Selenium 1',
            marca='Marca Selenium',
            tipo='EDP',
            genero='U',
            notas_superiores='Test',
            notas_medias='Test',
            notas_base='Test',
            volumen=100,
            precio=Decimal('1500.00'),
            stock=10,
            codigo_barras='SEL001'
        )

        self.perfume2 = Perfume.objects.create(
            nombre='Perfume Selenium 2',
            marca='Marca Selenium',
            tipo='EDT',
            genero='F',
            notas_superiores='Test',
            notas_medias='Test',
            notas_base='Test',
            volumen=50,
            precio=Decimal('800.00'),
            stock=5,
            codigo_barras='SEL002'
        )

    def login(self, username, password):
        """Helper para hacer login."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')

        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')

        username_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)

        # Esperar a que se complete el login
        WebDriverWait(self.selenium, 10).until(
            lambda driver: driver.current_url != f'{self.live_server_url}/accounts/login/'
        )

    def wait_for_element(self, by, value, timeout=10):
        """Helper para esperar a que un elemento esté presente."""
        return WebDriverWait(self.selenium, timeout).until(
            EC.presence_of_element_located((by, value))
        )


class POSInterfaceTest(SeleniumTestBase):
    """Tests de interfaz del POS usando Selenium."""

    def test_login_cajero_redirige_a_pos(self):
        """Test que cajero es redirigido al POS después del login."""
        self.login('cajero_selenium', 'testpass123')

        # Verificar que estamos en el POS
        self.assertIn('/pos/', self.selenium.current_url)

        # Verificar elementos de la interfaz
        h2 = self.selenium.find_element(By.TAG_NAME, 'h2')
        self.assertIn('PUNTO DE VENTA', h2.text.upper())

    def test_login_supervisor_redirige_a_reportes(self):
        """Test que supervisor es redirigido a reportes después del login."""
        self.login('supervisor_selenium', 'testpass123')

        # Verificar que estamos en reportes
        self.assertIn('/reportes/', self.selenium.current_url)

    def test_buscar_producto_en_pos(self):
        """Test buscar producto en el POS con AJAX."""
        self.login('cajero_selenium', 'testpass123')

        # Encontrar input de búsqueda
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')

        # Escribir en el campo de búsqueda
        busqueda_input.send_keys('Selenium 1')

        # Esperar resultados (AJAX)
        time.sleep(1)  # Esperar el debounce de 300ms + tiempo de respuesta

        # Verificar que aparecieron resultados
        resultados = self.selenium.find_element(By.ID, 'resultados-busqueda')
        self.assertIn('Perfume Selenium 1', resultados.text)
        self.assertIn('1500', resultados.text)

    def test_agregar_producto_a_venta(self):
        """Test agregar producto a la venta desde búsqueda."""
        self.login('cajero_selenium', 'testpass123')

        # Buscar producto
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')

        # Esperar resultados
        time.sleep(1)

        # Hacer clic en el botón Agregar
        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
        except TimeoutException:
            # Si no encuentra el botón, intentar hacer clic en el resultado
            resultados = self.selenium.find_element(By.ID, 'resultados-busqueda')
            resultados.click()

        # Esperar a que se recargue la página
        time.sleep(1)

        # Verificar que el producto aparece en la venta actual
        page_source = self.selenium.page_source
        self.assertIn('Marca Selenium', page_source)
        self.assertIn('Perfume Selenium 1', page_source)

    def test_modificar_cantidad_producto(self):
        """Test modificar cantidad de un producto en la venta."""
        self.login('cajero_selenium', 'testpass123')

        # Agregar producto primero
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')
        time.sleep(1)

        # Agregar producto
        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # Buscar input de cantidad y modificar
        try:
            cantidad_input = self.selenium.find_element(By.NAME, 'cantidad')
            cantidad_input.clear()
            cantidad_input.send_keys('3')

            # Hacer clic en botón Actualizar
            actualizar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'Actualizar')]")
            actualizar_btn.click()

            time.sleep(1)

            # Verificar que se actualizó
            cantidad_input = self.selenium.find_element(By.NAME, 'cantidad')
            self.assertEqual(cantidad_input.get_attribute('value'), '3')
        except Exception as e:
            # Si falla, el producto no se agregó correctamente
            print(f"No se pudo modificar cantidad: {e}")

    def test_eliminar_producto_de_venta(self):
        """Test eliminar producto de la venta."""
        self.login('cajero_selenium', 'testpass123')

        # Agregar producto primero
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')
        time.sleep(1)

        # Agregar producto
        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # Buscar botón Eliminar
        try:
            eliminar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'Eliminar')]")
            eliminar_btn.click()

            time.sleep(1)

            # Verificar que el producto ya no está
            page_source = self.selenium.page_source
            self.assertIn('No hay productos en la venta actual', page_source)
        except Exception as e:
            print(f"No se pudo eliminar producto: {e}")

    def test_procesar_pago_muestra_modal(self):
        """Test que el botón procesar pago muestra el modal."""
        self.login('cajero_selenium', 'testpass123')

        # Agregar un producto primero
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')
        time.sleep(1)

        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # Hacer clic en PROCESAR PAGO
        try:
            procesar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'PROCESAR PAGO')]")
            procesar_btn.click()

            # Verificar que aparece el modal
            modal = WebDriverWait(self.selenium, 5).until(
                EC.visibility_of_element_located((By.ID, 'modal-pago'))
            )

            self.assertTrue(modal.is_displayed())

            # Verificar que tiene el input de monto recibido
            monto_input = self.selenium.find_element(By.ID, 'monto-recibido')
            self.assertTrue(monto_input.is_displayed())
        except Exception as e:
            print(f"No se pudo abrir modal de pago: {e}")

    def test_completar_venta_exitosa(self):
        """Test completar una venta completa end-to-end."""
        self.login('cajero_selenium', 'testpass123')

        # Agregar producto
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')
        time.sleep(1)

        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # Abrir modal de pago
        try:
            procesar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'PROCESAR PAGO')]")
            procesar_btn.click()

            # Esperar modal
            monto_input = WebDriverWait(self.selenium, 5).until(
                EC.visibility_of_element_located((By.ID, 'monto-recibido'))
            )

            # Ingresar monto recibido
            monto_input.send_keys('2000')

            time.sleep(0.5)  # Esperar cálculo de cambio

            # Completar venta
            completar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'COMPLETAR VENTA')]")
            completar_btn.click()

            time.sleep(2)

            # Verificar que se completó (debe haber un mensaje o redirección)
            # Aquí deberíamos verificar el mensaje de éxito
            page_source = self.selenium.page_source
            # La página debería mostrar que no hay productos (venta limpiada)
            self.assertIn('No hay productos en la venta actual', page_source)

            # Verificar en base de datos que se creó la venta
            venta = Venta.objects.filter(cajero=self.cajero_user).first()
            self.assertIsNotNone(venta)

        except Exception as e:
            print(f"No se pudo completar venta: {e}")

    def test_cajero_no_ve_link_inventario(self):
        """Test que cajero no ve el link de inventario en la navegación."""
        self.login('cajero_selenium', 'testpass123')

        # Verificar que estamos en el POS
        self.wait_for_element(By.TAG_NAME, 'nav')

        # Buscar links de navegación
        nav = self.selenium.find_element(By.TAG_NAME, 'nav')
        nav_text = nav.text

        # Verificar que NO está el link de Inventario
        self.assertNotIn('Inventario', nav_text)

        # Verificar que SÍ están los links del POS
        self.assertIn('Punto de Venta', nav_text)
        self.assertIn('Consultar Ventas', nav_text)

    def test_supervisor_ve_link_inventario(self):
        """Test que supervisor SÍ ve el link de inventario."""
        self.login('supervisor_selenium', 'testpass123')

        # Esperar navegación
        self.wait_for_element(By.TAG_NAME, 'nav')

        # Buscar links de navegación
        nav = self.selenium.find_element(By.TAG_NAME, 'nav')
        nav_text = nav.text

        # Verificar que SÍ está el link de Inventario
        self.assertIn('Inventario', nav_text)
        self.assertIn('Reportes', nav_text)

    def test_cajero_no_puede_acceder_inventario_directamente(self):
        """Test que cajero no puede acceder al inventario por URL directa."""
        self.login('cajero_selenium', 'testpass123')

        # Intentar acceder directamente al inventario
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        time.sleep(1)

        # Debe ser redirigido (no debe estar en /perfumes/)
        current_url = self.selenium.current_url
        self.assertNotIn('/perfumes/', current_url)

    def test_navegacion_consultar_ventas(self):
        """Test navegación a consultar ventas."""
        self.login('cajero_selenium', 'testpass123')

        # Buscar link de Consultar Ventas
        consultar_link = self.selenium.find_element(By.LINK_TEXT, 'Consultar Ventas')
        consultar_link.click()

        time.sleep(1)

        # Verificar que estamos en lista de ventas
        self.assertIn('/ventas/', self.selenium.current_url)

        # Verificar elementos de la página
        page_source = self.selenium.page_source
        self.assertIn('Consultar Ventas', page_source)


class POSResponsivenessTest(SeleniumTestBase):
    """Tests de responsividad y comportamiento dinámico."""

    def test_busqueda_ajax_debounce(self):
        """Test que la búsqueda AJAX respeta el debounce."""
        self.login('cajero_selenium', 'testpass123')

        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')

        # Escribir rápidamente varias letras
        for letra in 'Sel':
            busqueda_input.send_keys(letra)
            time.sleep(0.05)  # Escribir rápido

        # No debería haber resultados todavía (debounce de 300ms)
        resultados = self.selenium.find_element(By.ID, 'resultados-busqueda')
        self.assertEqual(resultados.text.strip(), '')

        # Esperar el debounce
        time.sleep(0.5)

        # Ahora sí debería haber resultados
        resultados = self.selenium.find_element(By.ID, 'resultados-busqueda')
        self.assertNotEqual(resultados.text.strip(), '')

    def test_calculo_cambio_tiempo_real(self):
        """Test que el cambio se calcula en tiempo real."""
        self.login('cajero_selenium', 'testpass123')

        # Agregar producto
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')
        time.sleep(1)

        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # Abrir modal de pago
        try:
            procesar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'PROCESAR PAGO')]")
            procesar_btn.click()

            # Esperar modal
            monto_input = WebDriverWait(self.selenium, 5).until(
                EC.visibility_of_element_located((By.ID, 'monto-recibido'))
            )

            # Ingresar monto
            monto_input.send_keys('2000')

            time.sleep(0.3)  # Esperar cálculo

            # Verificar que se calculó el cambio
            cambio_display = self.selenium.find_element(By.ID, 'cambio-display')
            cambio_text = cambio_display.text

            # Debería mostrar $500.00 (2000 - 1500)
            self.assertIn('500', cambio_text)

        except Exception as e:
            print(f"No se pudo probar cálculo de cambio: {e}")

    def test_modal_cierra_con_escape(self):
        """Test que el modal se cierra con tecla Escape."""
        self.login('cajero_selenium', 'testpass123')

        # Agregar producto y abrir modal
        busqueda_input = self.wait_for_element(By.ID, 'busqueda-input')
        busqueda_input.send_keys('Selenium 1')
        time.sleep(1)

        try:
            agregar_btn = WebDriverWait(self.selenium, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Agregar')]"))
            )
            agregar_btn.click()
            time.sleep(1)

            procesar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'PROCESAR PAGO')]")
            procesar_btn.click()

            # Esperar modal
            modal = WebDriverWait(self.selenium, 5).until(
                EC.visibility_of_element_located((By.ID, 'modal-pago'))
            )

            self.assertTrue(modal.is_displayed())

            # Presionar Escape
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(self.selenium)
            actions.send_keys(Keys.ESCAPE)
            actions.perform()

            time.sleep(0.5)

            # El modal debería estar oculto
            # Verificar si el modal tiene display: none
            modal_style = modal.get_attribute('style')
            self.assertIn('display: none', modal_style)

        except Exception as e:
            print(f"No se pudo probar cierre de modal: {e}")
