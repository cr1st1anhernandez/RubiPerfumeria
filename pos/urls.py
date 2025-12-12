from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    # Vista principal del POS
    path('', views.pos_index, name='index'),

    # Gestión del carrito
    path('search/', views.search_product, name='search_product'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:product_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),

    # Checkout y ventas
    path('checkout/', views.checkout, name='checkout'),
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),

    # Productos
    path('products/', views.product_list, name='product_list'),

    # Inventario
    path('inventory/movement/', views.inventory_movement, name='inventory_movement'),
]
