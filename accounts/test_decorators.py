from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import UserProfile


class RoleBasedAccessTest(TestCase):
    """Test role-based access control."""

    def setUp(self):
        self.client = Client()

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123'
        )
        self.admin_user.profile.rol = 'ADMINISTRADOR'
        self.admin_user.profile.save()

        self.supervisor_user = User.objects.create_user(
            username='supervisor',
            password='supervisor123'
        )
        self.supervisor_user.profile.rol = 'SUPERVISOR'
        self.supervisor_user.profile.save()

        self.cajero_user = User.objects.create_user(
            username='cajero',
            password='cajero123'
        )
        self.cajero_user.profile.rol = 'CAJERO'
        self.cajero_user.profile.save()



class PerfumeCreateAccessTest(RoleBasedAccessTest):
    """Test access control for perfume creation."""

    def test_admin_can_create_perfume(self):
        """Test that administrators can access perfume creation."""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('perfume_create'))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_can_create_perfume(self):
        """Test that supervisors can access perfume creation."""
        self.client.login(username='supervisor', password='supervisor123')
        response = self.client.get(reverse('perfume_create'))
        self.assertEqual(response.status_code, 200)

    def test_cajero_cannot_create_perfume(self):
        """Test that cajeros cannot access perfume creation."""
        self.client.login(username='cajero', password='cajero123')
        response = self.client.get(reverse('perfume_create'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))


    def test_unauthenticated_cannot_create_perfume(self):
        """Test that unauthenticated users cannot access perfume creation."""
        response = self.client.get(reverse('perfume_create'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))


class PerfumeListAccessTest(RoleBasedAccessTest):
    """Test access control for perfume list."""

    def test_admin_can_view_perfume_list(self):
        """Test that administrators can view perfume list."""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('perfume_list'))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_can_view_perfume_list(self):
        """Test that supervisors can view perfume list."""
        self.client.login(username='supervisor', password='supervisor123')
        response = self.client.get(reverse('perfume_list'))
        self.assertEqual(response.status_code, 200)

    def test_cajero_cannot_view_perfume_list(self):
        """Test that cajeros cannot view perfume list (requires supervisor)."""
        self.client.login(username='cajero', password='cajero123')
        response = self.client.get(reverse('perfume_list'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))


    def test_unauthenticated_cannot_view_perfume_list(self):
        """Test that unauthenticated users cannot view perfume list."""
        response = self.client.get(reverse('perfume_list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))


class PerfumeUpdateDeleteAccessTest(RoleBasedAccessTest):
    """Test access control for perfume update and delete."""

    def setUp(self):
        super().setUp()
        from perfumes.models import Perfume
        self.perfume = Perfume.objects.create(
            nombre='Test Perfume',
            marca='Test Brand',
            tipo='EDP',
            genero='U',
            notas_superiores='Test top notes',
            notas_medias='Test middle notes',
            notas_base='Test base notes',
            volumen=100,
            precio=50.00,
            stock=10
        )

    def test_admin_can_update_perfume(self):
        """Test that administrators can update perfumes."""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('perfume_update', args=[self.perfume.pk]))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_can_update_perfume(self):
        """Test that supervisors can update perfumes."""
        self.client.login(username='supervisor', password='supervisor123')
        response = self.client.get(reverse('perfume_update', args=[self.perfume.pk]))
        self.assertEqual(response.status_code, 200)

    def test_cajero_cannot_update_perfume(self):
        """Test that cajeros cannot update perfumes."""
        self.client.login(username='cajero', password='cajero123')
        response = self.client.get(reverse('perfume_update', args=[self.perfume.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))


    def test_admin_can_delete_perfume(self):
        """Test that administrators can delete perfumes."""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('perfume_delete', args=[self.perfume.pk]))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_can_delete_perfume(self):
        """Test that supervisors can delete perfumes."""
        self.client.login(username='supervisor', password='supervisor123')
        response = self.client.get(reverse('perfume_delete', args=[self.perfume.pk]))
        self.assertEqual(response.status_code, 200)

    def test_cajero_cannot_delete_perfume(self):
        """Test that cajeros cannot delete perfumes."""
        self.client.login(username='cajero', password='cajero123')
        response = self.client.get(reverse('perfume_delete', args=[self.perfume.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

