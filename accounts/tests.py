from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileModelTest(TestCase):
    """Test UserProfile model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

    def test_user_profile_created_automatically(self):
        """Test that UserProfile is created automatically when User is created."""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, UserProfile)

    def test_user_profile_default_rol(self):
        """Test that default role is CAJERO."""
        self.assertEqual(self.user.profile.rol, 'CAJERO')

    def test_user_profile_str(self):
        """Test UserProfile string representation."""
        expected = f"{self.user.username} - Cajero"
        self.assertEqual(str(self.user.profile), expected)

    def test_es_administrador(self):
        """Test es_administrador method."""
        self.user.profile.rol = 'ADMINISTRADOR'
        self.user.profile.save()
        self.assertTrue(self.user.profile.es_administrador())

        self.user.profile.rol = 'SUPERVISOR'
        self.user.profile.save()
        self.assertFalse(self.user.profile.es_administrador())

    def test_es_supervisor(self):
        """Test es_supervisor method."""
        self.user.profile.rol = 'SUPERVISOR'
        self.user.profile.save()
        self.assertTrue(self.user.profile.es_supervisor())

        self.user.profile.rol = 'CAJERO'
        self.user.profile.save()
        self.assertFalse(self.user.profile.es_supervisor())

    def test_puede_gestionar_inventario(self):
        """Test puede_gestionar_inventario method."""
        self.user.profile.rol = 'ADMINISTRADOR'
        self.user.profile.save()
        self.assertTrue(self.user.profile.puede_gestionar_inventario())

        self.user.profile.rol = 'SUPERVISOR'
        self.user.profile.save()
        self.assertTrue(self.user.profile.puede_gestionar_inventario())

        self.user.profile.rol = 'CAJERO'
        self.user.profile.save()
        self.assertFalse(self.user.profile.puede_gestionar_inventario())

    def test_puede_vender(self):
        """Test puede_vender method."""
        roles = ['ADMINISTRADOR', 'SUPERVISOR', 'CAJERO']
        for rol in roles:
            self.user.profile.rol = rol
            self.user.profile.save()
            self.assertTrue(self.user.profile.puede_vender())


class LoginViewTest(TestCase):
    """Test login view."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )

    def test_login_page_loads(self):
        """Test that login page loads successfully."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_with_valid_credentials(self):
        """Test login with valid credentials."""
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)
        # Default role is CAJERO, should redirect to POS
        self.assertRedirects(response, reverse('pos:pos_principal'))

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o contraseña incorrectos.')

    def test_login_redirects_authenticated_user(self):
        """Test that authenticated users are redirected from login page."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))


class LogoutViewTest(TestCase):
    """Test logout view."""

    def setUp(self):
        self.client = Client()
        self.logout_url = reverse('logout')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_logout_requires_authentication(self):
        """Test that logout requires authentication."""
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_logout_redirects_to_login(self):
        """Test that logout redirects to login page."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))


class HomeViewTest(TestCase):
    """Test home view."""

    def setUp(self):
        self.client = Client()
        self.home_url = reverse('home')
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_home_requires_authentication(self):
        """Test that home page requires authentication."""
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_home_loads_for_authenticated_user(self):
        """Test that home page loads for authenticated users."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/home.html')

    def test_home_displays_user_info(self):
        """Test that home page displays user information."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(self.home_url)
        self.assertContains(response, 'testuser')
        self.assertContains(response, 'Cajero')
