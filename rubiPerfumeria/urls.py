from django.urls import path
from . import views

urlpatterns = [
    path('', views.perfume_list, name='perfume_list'),
    path('perfume/<int:pk>/', views.perfume_detail, name='perfume_detail'),
    path('perfume/crear/', views.perfume_create, name='perfume_create'),
    path('perfume/<int:pk>/editar/', views.perfume_update, name='perfume_update'),
    path('perfume/<int:pk>/eliminar/', views.perfume_delete, name='perfume_delete'),
]
