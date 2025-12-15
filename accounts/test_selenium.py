from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.models import User
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .models import UserProfile


class LoginSeleniumTest(StaticLiveServerTestCase):
    """Selenium tests for login functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.selenium = webdriver.Chrome(options=options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

    def test_login_page_loads(self):
        """Test that login page loads correctly."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        self.assertIn('Iniciar Sesión', self.selenium.page_source)
        self.assertIn('RubiPerfumeria', self.selenium.page_source)

    def test_login_with_valid_credentials(self):
        """Test login with valid credentials."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')

        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        username_input.send_keys('testuser')
        password_input.send_keys('testpass123')
        submit_button.click()

        # Wait for redirect to POS (default role is CAJERO)
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.url_contains('/pos/')
            )
            self.assertIn('/pos/', self.selenium.current_url)
        except TimeoutException:
            self.fail("Login did not redirect to POS")

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')

        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        username_input.send_keys('testuser')
        password_input.send_keys('wrongpassword')
        submit_button.click()

        # Wait for error message
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'message'))
            )
            self.assertIn('incorrectos', self.selenium.page_source.lower())
        except TimeoutException:
            self.fail("Error message did not appear")

    def test_logout_functionality(self):
        """Test logout functionality."""
        # First login
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        username_input.send_keys('testuser')
        password_input.send_keys('testpass123')
        submit_button.click()

        # Wait for login to complete (redirect to POS)
        WebDriverWait(self.selenium, 10).until(
            EC.url_contains('/pos/')
        )

        # Now logout
        self.selenium.get(f'{self.live_server_url}/accounts/logout/')

        # Wait for redirect to login page
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.url_contains('/accounts/login/')
            )
            self.assertIn('/accounts/login/', self.selenium.current_url)
        except TimeoutException:
            self.fail("Logout did not redirect to login page")

    def test_login_form_validation(self):
        """Test that login form has required fields."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')

        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')

        self.assertTrue(username_input.is_displayed())
        self.assertTrue(password_input.is_displayed())

    def test_authenticated_user_redirected_from_login(self):
        """Test that authenticated users are redirected from login page."""
        # First login
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        username_input.send_keys('testuser')
        password_input.send_keys('testpass123')
        submit_button.click()

        # Wait for redirect (to POS for CAJERO)
        WebDriverWait(self.selenium, 10).until(
            EC.url_contains('/pos/')
        )

        # Try to access login page again
        self.selenium.get(f'{self.live_server_url}/accounts/login/')

        # Should be redirected to home
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.url_contains('/accounts/home/')
            )
            self.assertIn('/accounts/home/', self.selenium.current_url)
        except TimeoutException:
            self.fail("Authenticated user was not redirected from login page")


class RoleBasedAccessSeleniumTest(StaticLiveServerTestCase):
    """Selenium tests for role-based access control."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.selenium = webdriver.Chrome(options=options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        self.admin_user.profile.rol = 'ADMINISTRADOR'
        self.admin_user.profile.save()

        # Create cajero user
        self.cajero_user = User.objects.create_user(
            username='cajero',
            password='cajero123'
        )
        self.cajero_user.profile.rol = 'CAJERO'
        self.cajero_user.profile.save()

    def login_as(self, username, password):
        """Helper method to login as a user."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        submit_button = self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]')

        username_input.send_keys(username)
        password_input.send_keys(password)
        submit_button.click()

        # Wait for redirect
        WebDriverWait(self.selenium, 10).until(
            EC.url_changes(f'{self.live_server_url}/accounts/login/')
        )

    def test_admin_can_access_create_perfume_button(self):
        """Test that admin can see create perfume button on home page."""
        self.login_as('admin', 'admin123')

        self.selenium.get(f'{self.live_server_url}/accounts/home/')

        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )

        # Check for create button
        page_source = self.selenium.page_source
        self.assertIn('Crear Perfume', page_source)

    def test_cajero_cannot_access_create_perfume_button(self):
        """Test that cajero cannot see create perfume button on home page."""
        self.login_as('cajero', 'cajero123')

        self.selenium.get(f'{self.live_server_url}/accounts/home/')

        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )

        # Check that create button is not present
        page_source = self.selenium.page_source
        self.assertNotIn('Crear Perfume', page_source)

    def test_cajero_redirected_from_create_perfume_page(self):
        """Test that cajero is redirected when accessing create perfume page."""
        self.login_as('cajero', 'cajero123')

        self.selenium.get(f'{self.live_server_url}/perfumes/perfume/crear/')

        # Wait for redirect
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.url_contains('/accounts/home/')
            )
            self.assertIn('/accounts/home/', self.selenium.current_url)
        except TimeoutException:
            self.fail("Vendedor was not redirected from create perfume page")

    def test_admin_can_access_create_perfume_page(self):
        """Test that admin can access create perfume page."""
        self.login_as('admin', 'admin123')

        self.selenium.get(f'{self.live_server_url}/perfumes/perfume/crear/')

        # Wait for page to load
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'form'))
            )
            self.assertIn('/perfumes/perfume/crear/', self.selenium.current_url)
        except TimeoutException:
            self.fail("Admin could not access create perfume page")

    def test_unauthenticated_redirected_to_login(self):
        """Test that unauthenticated users are redirected to login."""
        self.selenium.get(f'{self.live_server_url}/perfumes/')

        # Wait for redirect to login
        try:
            WebDriverWait(self.selenium, 10).until(
                EC.url_contains('/accounts/login/')
            )
            self.assertIn('/accounts/login/', self.selenium.current_url)
        except TimeoutException:
            self.fail("Unauthenticated user was not redirected to login")
