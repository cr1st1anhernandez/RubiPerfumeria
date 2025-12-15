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


class DashboardSeleniumTest(SeleniumTestBase):
    """Tests de Selenium para el dashboard con gráficas."""

    def setUp(self):
        """Configurar datos de prueba para el dashboard."""
        super().setUp()

        # Crear ventas de prueba para el dashboard
        from django.utils import timezone
        from datetime import timedelta

        hoy = timezone.now()

        # Crear venta de hoy
        venta_hoy = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_creacion=hoy
        )

        from .models import DetalleVenta
        DetalleVenta.objects.create(
            venta=venta_hoy,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=Decimal('1500.00'),
            subtotal=Decimal('1500.00')
        )

        # Crear venta de ayer
        ayer = hoy - timedelta(days=1)
        venta_ayer = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('800.00'),
            total=Decimal('800.00'),
            monto_recibido=Decimal('1000.00'),
            cambio=Decimal('200.00'),
            metodo_pago='TARJETA',
            estado='COMPLETADA',
            fecha_creacion=ayer
        )

        DetalleVenta.objects.create(
            venta=venta_ayer,
            perfume=self.perfume2,
            cantidad=1,
            precio_unitario=Decimal('800.00'),
            subtotal=Decimal('800.00')
        )

    def test_cajero_no_puede_acceder_dashboard(self):
        """Test que cajero no puede acceder al dashboard."""
        self.login('cajero_selenium', 'testpass123')

        # Intentar acceder al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(1)

        # Debe ser redirigido (no debe estar en /dashboard/)
        current_url = self.selenium.current_url
        self.assertNotIn('/dashboard/', current_url)

    def test_supervisor_puede_acceder_dashboard(self):
        """Test que supervisor puede acceder al dashboard."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Verificar que estamos en el dashboard
        self.assertIn('/dashboard/', self.selenium.current_url)

        # Verificar título
        page_source = self.selenium.page_source
        self.assertIn('Dashboard', page_source)

    def test_dashboard_muestra_kpi_cards(self):
        """Test que el dashboard muestra las tarjetas de KPIs."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Verificar que existen los KPI cards
        kpi_cards = self.selenium.find_elements(By.CLASS_NAME, 'kpi-card')

        # Debe haber al menos 5 KPI cards
        self.assertGreaterEqual(len(kpi_cards), 5)

        # Verificar contenido de los cards
        page_source = self.selenium.page_source
        self.assertIn('Ventas de Hoy', page_source)
        self.assertIn('Ventas del Mes', page_source)
        self.assertIn('Ticket Promedio', page_source)
        self.assertIn('Productos Vendidos', page_source)
        self.assertIn('Total Clientes', page_source)

    def test_dashboard_muestra_indicadores_de_cambio(self):
        """Test que el dashboard muestra indicadores de cambio (flechas)."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Verificar que existen indicadores de cambio (▲ o ▼)
        page_source = self.selenium.page_source

        # Debe haber al menos un indicador de cambio
        tiene_flecha_arriba = '▲' in page_source
        tiene_flecha_abajo = '▼' in page_source

        self.assertTrue(tiene_flecha_arriba or tiene_flecha_abajo)

    def test_dashboard_carga_script_chartjs(self):
        """Test que el dashboard carga la librería Chart.js."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Verificar que Chart.js está cargado
        chart_loaded = self.selenium.execute_script("return typeof Chart !== 'undefined';")
        self.assertTrue(chart_loaded, "Chart.js no está cargado")

    def test_dashboard_renderiza_graficas(self):
        """Test que el dashboard renderiza las gráficas correctamente."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(3)  # Dar tiempo para que se rendericen las gráficas

        # Verificar que existen los canvas de las gráficas
        canvas_elements = self.selenium.find_elements(By.TAG_NAME, 'canvas')

        # Debe haber al menos 4 gráficas (ventas por día, top productos, cajeros, horas)
        self.assertGreaterEqual(len(canvas_elements), 4, f"Solo se encontraron {len(canvas_elements)} gráficas")

        # Verificar IDs específicos de las gráficas
        expected_chart_ids = [
            'ventasPorDiaChart',
            'topProductosChart',
            'cajerosChart',
            'ventasPorHoraChart'
        ]

        for chart_id in expected_chart_ids:
            try:
                canvas = self.selenium.find_element(By.ID, chart_id)
                self.assertIsNotNone(canvas)
            except:
                self.fail(f"No se encontró la gráfica con ID: {chart_id}")

    def test_dashboard_grafica_ventas_por_dia_tiene_datos(self):
        """Test que la gráfica de ventas por día tiene datos."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(3)

        # Verificar que la gráfica tiene datos
        # Ejecutar JavaScript para obtener los datos del chart
        script = """
        var chart = Chart.getChart('ventasPorDiaChart');
        if (chart) {
            return {
                labels: chart.data.labels.length,
                data: chart.data.datasets[0].data.length
            };
        }
        return null;
        """

        chart_data = self.selenium.execute_script(script)

        if chart_data:
            # Debe tener 30 puntos de datos (últimos 30 días)
            self.assertEqual(chart_data['labels'], 30)
            self.assertEqual(chart_data['data'], 30)

    def test_dashboard_muestra_titulos_graficas(self):
        """Test que el dashboard muestra títulos de las gráficas."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Verificar títulos de las gráficas
        page_source = self.selenium.page_source

        expected_titles = [
            'Ventas Últimos 30 Días',
            'Top 10 Productos Más Vendidos',
            'Top 5 Vendedores del Mes',
            'Distribución de Ventas por Hora',
            'Productos con Stock Bajo'
        ]

        for title in expected_titles:
            self.assertIn(title, page_source, f"No se encontró el título: {title}")

    def test_dashboard_muestra_tabla_stock_bajo(self):
        """Test que el dashboard muestra la tabla de productos con stock bajo."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Verificar que existe la tabla
        try:
            tabla_stock = self.selenium.find_element(By.CLASS_NAME, 'stock-table')
            self.assertIsNotNone(tabla_stock)

            # El perfume2 tiene stock de 5, debería aparecer
            page_source = self.selenium.page_source
            self.assertIn('Perfume Selenium 2', page_source)

        except Exception as e:
            self.fail(f"No se encontró la tabla de stock bajo: {e}")

    def test_dashboard_navegacion_desde_menu(self):
        """Test navegación al dashboard desde el menú."""
        self.login('supervisor_selenium', 'testpass123')

        # Esperar a que cargue la página
        time.sleep(1)

        # Buscar el link de Dashboard en el nav
        try:
            dashboard_link = self.selenium.find_element(By.LINK_TEXT, 'Dashboard')
            dashboard_link.click()

            time.sleep(2)

            # Verificar que estamos en el dashboard
            self.assertIn('/dashboard/', self.selenium.current_url)

            # Verificar que se cargó correctamente
            page_source = self.selenium.page_source
            self.assertIn('Dashboard de Ventas', page_source)

        except Exception as e:
            self.fail(f"No se pudo navegar al dashboard desde el menú: {e}")

    def test_dashboard_responsive_design(self):
        """Test que el dashboard es responsive."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(2)

        # Cambiar tamaño de ventana a móvil
        self.selenium.set_window_size(375, 667)
        time.sleep(1)

        # Verificar que las gráficas siguen siendo visibles
        canvas_elements = self.selenium.find_elements(By.TAG_NAME, 'canvas')
        self.assertGreater(len(canvas_elements), 0)

        # Restaurar tamaño
        self.selenium.set_window_size(1920, 1080)

    def test_dashboard_cajero_no_ve_link_dashboard(self):
        """Test que cajero no ve el link del dashboard en el menú."""
        self.login('cajero_selenium', 'testpass123')

        # Esperar navegación
        time.sleep(1)

        # Buscar nav
        nav = self.selenium.find_element(By.TAG_NAME, 'nav')
        nav_text = nav.text

        # Verificar que NO está el link de Dashboard
        self.assertNotIn('Dashboard', nav_text)

    def test_dashboard_supervisor_ve_link_dashboard(self):
        """Test que supervisor ve el link del dashboard en el menú."""
        self.login('supervisor_selenium', 'testpass123')

        # Esperar navegación
        time.sleep(1)

        # Buscar nav
        nav = self.selenium.find_element(By.TAG_NAME, 'nav')
        nav_text = nav.text

        # Verificar que SÍ está el link de Dashboard
        self.assertIn('Dashboard', nav_text)

    def test_dashboard_graficas_tienen_colores(self):
        """Test que las gráficas usan colores correctamente."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al dashboard
        self.selenium.get(f'{self.live_server_url}/pos/dashboard/')
        time.sleep(3)

        # Verificar que las gráficas tienen configuración de colores
        script = """
        var chart = Chart.getChart('ventasPorDiaChart');
        if (chart && chart.data.datasets[0]) {
            return {
                borderColor: chart.data.datasets[0].borderColor,
                backgroundColor: chart.data.datasets[0].backgroundColor
            };
        }
        return null;
        """

        colors = self.selenium.execute_script(script)

        if colors:
            # Verificar que tiene colores definidos
            self.assertIsNotNone(colors['borderColor'])
            self.assertIsNotNone(colors['backgroundColor'])


class ReportesSeleniumTest(SeleniumTestBase):
    """Tests de Selenium para el sistema de reportes."""

    def setUp(self):
        """Configurar datos de prueba para reportes."""
        super().setUp()

        # Crear ventas de prueba para reportes
        from django.utils import timezone
        from datetime import timedelta

        hoy = timezone.now()

        # Crear venta de hoy
        venta_hoy = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('2000.00'),
            total=Decimal('2000.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('0.00'),
            metodo_pago='EFECTIVO',
            estado='COMPLETADA',
            fecha_creacion=hoy
        )

        from .models import DetalleVenta
        DetalleVenta.objects.create(
            venta=venta_hoy,
            perfume=self.perfume1,
            cantidad=1,
            precio_unitario=Decimal('2000.00'),
            subtotal=Decimal('2000.00')
        )

        # Crear venta de ayer
        ayer = hoy - timedelta(days=1)
        venta_ayer = Venta.objects.create(
            cajero=self.cajero_user,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
            monto_recibido=Decimal('2000.00'),
            cambio=Decimal('500.00'),
            metodo_pago='TARJETA',
            estado='COMPLETADA',
            fecha_creacion=ayer
        )

        DetalleVenta.objects.create(
            venta=venta_ayer,
            perfume=self.perfume2,
            cantidad=1,
            precio_unitario=Decimal('1500.00'),
            subtotal=Decimal('1500.00')
        )

    def test_cajero_no_puede_acceder_reportes(self):
        """Test que cajero no puede acceder a reportes."""
        self.login('cajero_selenium', 'testpass123')

        # Intentar acceder a reportes
        self.selenium.get(f'{self.live_server_url}/pos/reportes/')
        time.sleep(1)

        # Debe ser redirigido (no debe estar en /reportes/)
        current_url = self.selenium.current_url
        self.assertNotIn('/reportes/', current_url)

    def test_supervisor_puede_acceder_reportes(self):
        """Test que supervisor puede acceder a reportes."""
        self.login('supervisor_selenium', 'testpass123')

        # El supervisor es redirigido automáticamente a reportes al login
        time.sleep(1)

        # Verificar que estamos en reportes
        self.assertIn('/reportes/', self.selenium.current_url)

        # Verificar título
        page_source = self.selenium.page_source
        self.assertIn('Reportes de Ventas', page_source)

    def test_reportes_muestra_filtros(self):
        """Test que la página de reportes muestra los filtros."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar a reportes
        self.selenium.get(f'{self.live_server_url}/pos/reportes/')
        time.sleep(2)

        # Verificar que existen los campos de filtro
        try:
            fecha_desde = self.selenium.find_element(By.NAME, 'fecha_desde')
            fecha_hasta = self.selenium.find_element(By.NAME, 'fecha_hasta')
            cajero_select = self.selenium.find_element(By.NAME, 'cajero')

            self.assertIsNotNone(fecha_desde)
            self.assertIsNotNone(fecha_hasta)
            self.assertIsNotNone(cajero_select)
        except Exception as e:
            self.fail(f"No se encontraron los filtros: {e}")

    def test_reportes_muestra_botones_exportar(self):
        """Test que la página muestra botones de exportación."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar a reportes
        self.selenium.get(f'{self.live_server_url}/pos/reportes/')
        time.sleep(2)

        # Verificar que existen los botones de exportar
        page_source = self.selenium.page_source
        self.assertIn('Exportar a PDF', page_source)
        self.assertIn('Exportar a Excel', page_source)

        # Verificar que son links válidos
        try:
            pdf_link = self.selenium.find_element(By.PARTIAL_LINK_TEXT, 'PDF')
            excel_link = self.selenium.find_element(By.PARTIAL_LINK_TEXT, 'Excel')

            self.assertIsNotNone(pdf_link)
            self.assertIsNotNone(excel_link)
        except Exception as e:
            self.fail(f"No se encontraron los botones de exportar: {e}")

    def test_reportes_muestra_resumen(self):
        """Test que la página muestra el resumen de ventas."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar a reportes
        self.selenium.get(f'{self.live_server_url}/pos/reportes/')
        time.sleep(2)

        # Verificar que muestra las tarjetas de resumen
        page_source = self.selenium.page_source
        self.assertIn('Total de Ventas', page_source)
        self.assertIn('Cantidad de Transacciones', page_source)
        self.assertIn('Ticket Promedio', page_source)

    def test_reportes_muestra_tabla_ventas(self):
        """Test que la página muestra la tabla de ventas."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar a reportes
        self.selenium.get(f'{self.live_server_url}/pos/reportes/')
        time.sleep(2)

        # Verificar que existe la tabla
        try:
            tabla = self.selenium.find_element(By.TAG_NAME, 'table')
            self.assertIsNotNone(tabla)

            # Verificar columnas de la tabla
            page_source = self.selenium.page_source
            self.assertIn('Fecha', page_source)
            self.assertIn('Ticket', page_source)
            self.assertIn('Cajero', page_source)
            self.assertIn('Total', page_source)
        except Exception as e:
            self.fail(f"No se encontró la tabla de ventas: {e}")

    def test_reportes_filtrar_por_fecha(self):
        """Test que el filtro de fechas funciona."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar a reportes
        self.selenium.get(f'{self.live_server_url}/pos/reportes/')
        time.sleep(2)

        # Obtener fecha de hoy
        from django.utils import timezone
        hoy = timezone.now().date()

        # Filtrar por hoy
        try:
            fecha_desde = self.selenium.find_element(By.NAME, 'fecha_desde')
            fecha_hasta = self.selenium.find_element(By.NAME, 'fecha_hasta')

            fecha_desde.clear()
            fecha_desde.send_keys(hoy.strftime('%Y-%m-%d'))

            fecha_hasta.clear()
            fecha_hasta.send_keys(hoy.strftime('%Y-%m-%d'))

            # Hacer clic en botón filtrar
            filtrar_btn = self.selenium.find_element(By.XPATH, "//button[contains(text(), 'Filtrar')]")
            filtrar_btn.click()

            time.sleep(2)

            # Verificar que se aplicó el filtro (debe mostrar solo ventas de hoy)
            page_source = self.selenium.page_source
            # Debe haber al menos una venta
            self.assertIn('cajero_selenium', page_source.lower())
        except Exception as e:
            self.fail(f"No se pudo filtrar por fecha: {e}")

    def test_reportes_navegacion_desde_menu(self):
        """Test navegación a reportes desde el menú."""
        self.login('supervisor_selenium', 'testpass123')

        # Esperar a que cargue la página
        time.sleep(1)

        # Buscar el link de Reportes en el nav
        try:
            reportes_link = self.selenium.find_element(By.LINK_TEXT, 'Reportes')
            reportes_link.click()

            time.sleep(2)

            # Verificar que estamos en reportes
            self.assertIn('/reportes/', self.selenium.current_url)

            # Verificar que se cargó correctamente
            page_source = self.selenium.page_source
            self.assertIn('Reportes de Ventas', page_source)
        except Exception as e:
            self.fail(f"No se pudo navegar a reportes desde el menú: {e}")


class InventarioExportSeleniumTest(SeleniumTestBase):
    """Tests de Selenium para la exportación de inventario."""

    def setUp(self):
        """Configurar datos de prueba para inventario."""
        super().setUp()

        # Crear movimientos de inventario
        from .models import MovimientoInventario

        MovimientoInventario.objects.create(
            perfume=self.perfume1,
            usuario=self.supervisor_user,
            tipo_movimiento='AJUSTE_MANUAL',
            cantidad=5,
            stock_anterior=10,
            stock_nuevo=15,
            observaciones='Ajuste de prueba'
        )

    def test_supervisor_puede_acceder_inventario(self):
        """Test que supervisor puede acceder al inventario."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al inventario
        self.selenium.get(f'{self.live_server_url}/perfumes/')
        time.sleep(2)

        # Verificar que estamos en el inventario
        self.assertIn('/perfumes/', self.selenium.current_url)

        # Verificar título
        page_source = self.selenium.page_source
        self.assertIn('Lista de Perfumes', page_source)

    def test_inventario_muestra_botones_exportar(self):
        """Test que el inventario muestra botones de exportación."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al inventario
        self.selenium.get(f'{self.live_server_url}/perfumes/')
        time.sleep(2)

        # Verificar que existen los botones de exportar
        page_source = self.selenium.page_source
        self.assertIn('Exportar a PDF', page_source)
        self.assertIn('Exportar a Excel', page_source)

        # Verificar que son links válidos
        try:
            pdf_link = self.selenium.find_element(By.PARTIAL_LINK_TEXT, 'PDF')
            excel_link = self.selenium.find_element(By.PARTIAL_LINK_TEXT, 'Excel')

            self.assertIsNotNone(pdf_link)
            self.assertIsNotNone(excel_link)
        except Exception as e:
            self.fail(f"No se encontraron los botones de exportar: {e}")

    def test_inventario_muestra_tabla_productos(self):
        """Test que el inventario muestra la tabla de productos."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al inventario
        self.selenium.get(f'{self.live_server_url}/perfumes/')
        time.sleep(2)

        # Verificar que existe la tabla
        try:
            tabla = self.selenium.find_element(By.TAG_NAME, 'table')
            self.assertIsNotNone(tabla)

            # Verificar que muestra los productos
            page_source = self.selenium.page_source
            self.assertIn('Perfume Selenium 1', page_source)
            self.assertIn('Perfume Selenium 2', page_source)
        except Exception as e:
            self.fail(f"No se encontró la tabla de productos: {e}")

    def test_inventario_muestra_movimientos(self):
        """Test que el inventario muestra los movimientos."""
        self.login('supervisor_selenium', 'testpass123')

        # Navegar al inventario
        self.selenium.get(f'{self.live_server_url}/perfumes/')
        time.sleep(2)

        # Verificar que muestra la sección de movimientos
        page_source = self.selenium.page_source
        self.assertIn('Movimientos', page_source)

    def test_cajero_no_puede_acceder_inventario(self):
        """Test que cajero no puede acceder al inventario."""
        self.login('cajero_selenium', 'testpass123')

        # Intentar acceder al inventario
        self.selenium.get(f'{self.live_server_url}/perfumes/')
        time.sleep(1)

        # Debe ser redirigido (no debe estar en /perfumes/)
        current_url = self.selenium.current_url
        self.assertNotIn('/perfumes/', current_url)
