"""
Tests para verificar que los templates se renderizan correctamente
con el diseño unificado y las condiciones de navegación
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import UserProfile


class NavigationTemplateTestCase(TestCase):
    """Tests para verificar la navegación en los templates"""

    def setUp(self):
        """Configurar usuarios con diferentes roles para testing"""
        # Usuario Administrador
        self.admin_user = User.objects.create_user(
            username='admin_test',
            password='admin123'
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            rol='ADMINISTRADOR'
        )

        # Usuario Supervisor
        self.supervisor_user = User.objects.create_user(
            username='supervisor_test',
            password='super123'
        )
        self.supervisor_profile = UserProfile.objects.create(
            user=self.supervisor_user,
            rol='SUPERVISOR'
        )

        # Usuario Cajero
        self.cajero_user = User.objects.create_user(
            username='cajero_test',
            password='cajero123'
        )
        self.cajero_profile = UserProfile.objects.create(
            user=self.cajero_user,
            rol='CAJERO'
        )

        self.client = Client()

    def test_admin_sees_dashboard_link_in_navigation(self):
        """El administrador ve el enlace al dashboard en la navegación"""
        self.client.login(username='admin_test', password='admin123')
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, reverse('pos:dashboard'))

    def test_supervisor_sees_dashboard_link_in_navigation(self):
        """El supervisor ve el enlace al dashboard en la navegación"""
        self.client.login(username='supervisor_test', password='super123')
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, reverse('pos:dashboard'))

    def test_cajero_does_not_see_dashboard_link(self):
        """El cajero NO ve el enlace al dashboard en la navegación"""
        self.client.login(username='cajero_test', password='cajero123')
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        # Verificar que NO contiene el enlace al dashboard
        self.assertNotContains(response, reverse('pos:dashboard'))

    def test_profile_attribute_is_accessible(self):
        """Verificar que user.profile es accesible correctamente"""
        self.client.login(username='admin_test', password='admin123')
        response = self.client.get(reverse('pos:index'))

        # El template debería renderizarse sin errores
        self.assertEqual(response.status_code, 200)
        # El usuario debería estar en el contexto
        self.assertTrue(response.context['user'].is_authenticated)
        # El profile debería ser accesible
        self.assertEqual(response.context['user'].profile.rol, 'ADMINISTRADOR')


class CSSLoadingTestCase(TestCase):
    """Tests para verificar que el CSS se carga correctamente"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_user',
            password='test123'
        )
        UserProfile.objects.create(user=self.user, rol='CAJERO')
        self.client = Client()
        self.client.login(username='test_user', password='test123')

    def test_css_file_is_linked_in_pos_templates(self):
        """Verificar que el CSS está vinculado en los templates POS"""
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pos/css/style.css')

    def test_css_file_is_linked_in_accounts_templates(self):
        """Verificar que el CSS está vinculado en los templates de accounts"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pos/css/style.css')

    def test_templates_use_unified_card_structure(self):
        """Verificar que los templates usan la estructura de cards unificada"""
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.status_code, 200)
        # Verificar que usa las clases CSS unificadas
        self.assertContains(response, 'content-wrapper')
        self.assertContains(response, 'card')
        self.assertContains(response, 'card-header')
        self.assertContains(response, 'card-body')

    def test_buttons_use_unified_classes(self):
        """Verificar que los botones usan las clases CSS unificadas"""
        response = self.client.get(reverse('pos:index'))
        self.assertEqual(response.status_code, 200)
        # Verificar que usa las clases de botones
        self.assertContains(response, 'class="button')


class ReportTemplatesTestCase(TestCase):
    """Tests para verificar que los templates de reportes funcionan correctamente"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_user',
            password='test123'
        )
        UserProfile.objects.create(user=self.user, rol='ADMINISTRADOR')
        self.client = Client()
        self.client.login(username='test_user', password='test123')

    def test_sales_report_template_renders_correctly(self):
        """Verificar que el template de reporte de ventas se renderiza"""
        response = self.client.get(reverse('pos:sales_report'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reporte de Ventas')
        self.assertContains(response, 'pos/css/style.css')

    def test_inventory_report_template_renders_correctly(self):
        """Verificar que el template de reporte de inventario se renderiza"""
        response = self.client.get(reverse('pos:inventory_report'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reporte de Inventario')
        self.assertContains(response, 'pos/css/style.css')
