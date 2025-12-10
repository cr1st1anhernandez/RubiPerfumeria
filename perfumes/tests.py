from django.test import TestCase, Client, LiveServerTestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Perfume
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
import time


# ==================== TESTS UNITARIOS DEL MODELO ====================

class PerfumeModelTest(TestCase):
    def setUp(self):
        self.perfume = Perfume.objects.create(
            nombre="Sauvage",
            marca="Dior",
            descripcion="Fragancia fresca y especiada",
            codigo_barras="3348901419369",
            tipo="EDT",
            genero="M",
            notas_superiores="Bergamota, Pimienta",
            notas_medias="Lavanda, Geranio",
            notas_base="Ambroxan, Vainilla",
            volumen=100,
            concentracion=Decimal("12.50"),
            anio_lanzamiento=2015,
            precio=Decimal("95.00"),
            stock=50
        )

    def test_perfume_creation(self):
        self.assertEqual(self.perfume.nombre, "Sauvage")
        self.assertEqual(self.perfume.marca, "Dior")
        self.assertEqual(self.perfume.tipo, "EDT")
        self.assertEqual(self.perfume.genero, "M")
        self.assertEqual(self.perfume.volumen, 100)
        self.assertEqual(self.perfume.precio, Decimal("95.00"))
        self.assertEqual(self.perfume.stock, 50)

    def test_perfume_str_method(self):
        expected = "Dior - Sauvage (100ml)"
        self.assertEqual(str(self.perfume), expected)

    def test_esta_en_stock_method(self):
        self.assertTrue(self.perfume.esta_en_stock())

        self.perfume.stock = 0
        self.assertFalse(self.perfume.esta_en_stock())

    def test_perfume_ordering(self):
        perfume2 = Perfume.objects.create(
            nombre="Acqua di Gio",
            marca="Armani",
            notas_superiores="Naranja, Lima",
            notas_medias="Jazmín, Romero",
            notas_base="Almizcle, Cedro",
            volumen=50,
            precio=Decimal("80.00"),
            stock=30
        )

        perfumes = Perfume.objects.all()
        self.assertEqual(perfumes[0], perfume2)
        self.assertEqual(perfumes[1], self.perfume)

    def test_codigo_barras_unique(self):
        with self.assertRaises(Exception):
            Perfume.objects.create(
                nombre="Otro Perfume",
                marca="Otra Marca",
                codigo_barras="3348901419369",
                notas_superiores="Test",
                notas_medias="Test",
                notas_base="Test",
                volumen=50,
                precio=Decimal("50.00")
            )

    def test_precio_no_negativo(self):
        perfume = Perfume(
            nombre="Test",
            marca="Test",
            notas_superiores="Test",
            notas_medias="Test",
            notas_base="Test",
            volumen=50,
            precio=Decimal("-10.00"),
            stock=10
        )
        with self.assertRaises(ValidationError):
            perfume.full_clean()

    def test_stock_no_negativo(self):
        perfume = Perfume(
            nombre="Test",
            marca="Test",
            notas_superiores="Test",
            notas_medias="Test",
            notas_base="Test",
            volumen=50,
            precio=Decimal("50.00"),
            stock=-5
        )
        with self.assertRaises(ValidationError):
            perfume.full_clean()

    def test_volumen_minimo(self):
        perfume = Perfume(
            nombre="Test",
            marca="Test",
            notas_superiores="Test",
            notas_medias="Test",
            notas_base="Test",
            volumen=0,
            precio=Decimal("50.00"),
            stock=10
        )
        with self.assertRaises(ValidationError):
            perfume.full_clean()

    def test_concentracion_rango(self):
        perfume = Perfume(
            nombre="Test",
            marca="Test",
            notas_superiores="Test",
            notas_medias="Test",
            notas_base="Test",
            volumen=50,
            concentracion=Decimal("150.00"),
            precio=Decimal("50.00"),
            stock=10
        )
        with self.assertRaises(ValidationError):
            perfume.full_clean()

    def test_metadata_fields(self):
        self.assertIsNotNone(self.perfume.fecha_creacion)
        self.assertIsNotNone(self.perfume.fecha_actualizacion)


# ==================== TESTS CON DJANGO TEST CLIENT ====================

class PerfumeViewsTestClient(TestCase):
    def setUp(self):
        self.client = Client()
        # Crear usuario con rol de SUPERVISOR para poder acceder a todas las vistas
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.user.profile.rol = 'SUPERVISOR'
        self.user.profile.save()
        # Autenticar el cliente
        self.client.login(username='testuser', password='testpass123')

        self.perfume1 = Perfume.objects.create(
            nombre="Sauvage",
            marca="Dior",
            tipo="EDT",
            genero="M",
            notas_superiores="Bergamota",
            notas_medias="Lavanda",
            notas_base="Ambroxan",
            volumen=100,
            precio=Decimal("95.00"),
            stock=50
        )
        self.perfume2 = Perfume.objects.create(
            nombre="Chanel No 5",
            marca="Chanel",
            tipo="EDP",
            genero="F",
            notas_superiores="Neroli, Aldehídos",
            notas_medias="Jazmín, Rosa",
            notas_base="Vainilla, Vetiver",
            volumen=100,
            precio=Decimal("120.00"),
            stock=30
        )

    def test_perfume_list_view(self):
        response = self.client.get(reverse('perfume_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'perfumes/perfume_list.html')
        self.assertContains(response, "Sauvage")
        self.assertContains(response, "Chanel No 5")
        self.assertEqual(len(response.context['perfumes']), 2)

    def test_perfume_detail_view(self):
        response = self.client.get(reverse('perfume_detail', args=[self.perfume1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'perfumes/perfume_detail.html')
        self.assertContains(response, "Sauvage")
        self.assertContains(response, "Dior")
        self.assertContains(response, "Bergamota")

    def test_perfume_detail_view_not_found(self):
        response = self.client.get(reverse('perfume_detail', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_perfume_create_view_get(self):
        response = self.client.get(reverse('perfume_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'perfumes/perfume_form.html')
        self.assertContains(response, "Crear")

    def test_perfume_create_view_post_valid(self):
        data = {
            'nombre': 'Acqua di Gio',
            'marca': 'Armani',
            'tipo': 'EDT',
            'genero': 'M',
            'notas_superiores': 'Naranja, Lima',
            'notas_medias': 'Jazmín, Romero',
            'notas_base': 'Almizcle, Cedro',
            'volumen': 50,
            'precio': '80.00',
            'stock': 25
        }
        response = self.client.post(reverse('perfume_create'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Perfume.objects.count(), 3)
        new_perfume = Perfume.objects.get(nombre='Acqua di Gio')
        self.assertEqual(new_perfume.marca, 'Armani')

    def test_perfume_create_view_post_invalid(self):
        data = {
            'nombre': 'Test',
            'marca': 'Test',
            'notas_superiores': 'Test',
            'notas_medias': 'Test',
            'notas_base': 'Test',
            'volumen': -10,
            'precio': '50.00',
            'stock': 10
        }
        response = self.client.post(reverse('perfume_create'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Perfume.objects.count(), 2)

    def test_perfume_update_view_get(self):
        response = self.client.get(reverse('perfume_update', args=[self.perfume1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'perfumes/perfume_form.html')
        self.assertContains(response, "Editar")
        self.assertContains(response, "Sauvage")

    def test_perfume_update_view_post_valid(self):
        data = {
            'nombre': 'Sauvage Elixir',
            'marca': 'Dior',
            'tipo': 'PARFUM',
            'genero': 'M',
            'notas_superiores': 'Bergamota',
            'notas_medias': 'Lavanda',
            'notas_base': 'Ambroxan',
            'volumen': 100,
            'precio': '150.00',
            'stock': 40
        }
        response = self.client.post(reverse('perfume_update', args=[self.perfume1.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.perfume1.refresh_from_db()
        self.assertEqual(self.perfume1.nombre, 'Sauvage Elixir')
        self.assertEqual(self.perfume1.precio, Decimal('150.00'))

    def test_perfume_delete_view_get(self):
        response = self.client.get(reverse('perfume_delete', args=[self.perfume1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'perfumes/perfume_confirm_delete.html')
        self.assertContains(response, "Sauvage")

    def test_perfume_delete_view_post(self):
        response = self.client.post(reverse('perfume_delete', args=[self.perfume1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Perfume.objects.count(), 1)
        self.assertFalse(Perfume.objects.filter(pk=self.perfume1.pk).exists())

    def test_root_url_redirects_to_perfume_list(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/perfumes/', fetch_redirect_response=False)


# ==================== TESTS CON SELENIUM ====================

class PerfumeSeleniumTest(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            cls.selenium = webdriver.Chrome(options=options)
            cls.selenium.implicitly_wait(10)
        except WebDriverException:
            cls.selenium = None

    @classmethod
    def tearDownClass(cls):
        if cls.selenium:
            cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        if not self.selenium:
            self.skipTest("Selenium WebDriver no disponible")

        # Crear usuario con rol SUPERVISOR
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.user.profile.rol = 'SUPERVISOR'
        self.user.profile.save()

        # Login con Selenium
        self.login_selenium()

        self.perfume = Perfume.objects.create(
            nombre="Sauvage",
            marca="Dior",
            tipo="EDT",
            genero="M",
            notas_superiores="Bergamota",
            notas_medias="Lavanda",
            notas_base="Ambroxan",
            volumen=100,
            precio=Decimal("95.00"),
            stock=50
        )

    def login_selenium(self):
        """Helper method to login with Selenium."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        username_input.send_keys('testuser')
        password_input.send_keys('testpass123')
        submit_button.click()

        # Wait for login to complete
        WebDriverWait(self.selenium, 10).until(
            EC.url_changes(f'{self.live_server_url}/accounts/login/')
        )

    def test_selenium_list_perfumes(self):
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h2"))
        )

        self.assertIn("Lista de Perfumes", self.selenium.page_source)
        self.assertIn("Sauvage", self.selenium.page_source)
        self.assertIn("Dior", self.selenium.page_source)

    def test_selenium_view_perfume_detail(self):
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        ver_link = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Ver"))
        )
        ver_link.click()

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h2"))
        )

        self.assertIn("Detalle del Perfume", self.selenium.page_source)
        self.assertIn("Sauvage", self.selenium.page_source)
        self.assertIn("Bergamota", self.selenium.page_source)

    def test_selenium_create_perfume(self):
        self.selenium.get(f'{self.live_server_url}/perfumes/perfume/crear/')

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "nombre"))
        )

        self.selenium.find_element(By.NAME, "nombre").send_keys("Acqua di Gio")
        self.selenium.find_element(By.NAME, "marca").send_keys("Armani")
        self.selenium.find_element(By.NAME, "notas_superiores").send_keys("Naranja")
        self.selenium.find_element(By.NAME, "notas_medias").send_keys("Jazmín")
        self.selenium.find_element(By.NAME, "notas_base").send_keys("Almizcle")
        self.selenium.find_element(By.NAME, "volumen").send_keys("50")
        self.selenium.find_element(By.NAME, "precio").send_keys("80.00")
        self.selenium.find_element(By.NAME, "stock").send_keys("25")

        submit_button = self.selenium.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()

        time.sleep(1)

        self.assertEqual(Perfume.objects.count(), 2)
        self.assertTrue(Perfume.objects.filter(nombre="Acqua di Gio").exists())

    def test_selenium_update_perfume(self):
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        editar_link = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Editar"))
        )
        editar_link.click()

        nombre_field = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "nombre"))
        )
        nombre_field.clear()
        nombre_field.send_keys("Sauvage Elixir")

        precio_field = self.selenium.find_element(By.NAME, "precio")
        precio_field.clear()
        precio_field.send_keys("150.00")

        submit_button = self.selenium.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()

        time.sleep(1)

        self.perfume.refresh_from_db()
        self.assertEqual(self.perfume.nombre, "Sauvage Elixir")
        self.assertEqual(self.perfume.precio, Decimal("150.00"))

    def test_selenium_delete_perfume(self):
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        eliminar_link = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Eliminar"))
        )
        eliminar_link.click()

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button[type='submit']"))
        )

        self.assertIn("Confirmar Eliminacion", self.selenium.page_source)

        submit_button = self.selenium.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()

        time.sleep(1)

        self.assertEqual(Perfume.objects.count(), 0)

    def test_selenium_navigation(self):
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        agregar_link = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Agregar Perfume"))
        )
        agregar_link.click()

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.NAME, "nombre"))
        )

        self.assertIn("Crear Perfume", self.selenium.page_source)

        lista_link = self.selenium.find_element(By.LINK_TEXT, "Lista de Perfumes")
        lista_link.click()

        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        self.assertIn("Lista de Perfumes", self.selenium.page_source)
