# 🗺️ Guía de Navegación - RubiPerfumeria POS

## 📍 Mapa Completo de URLs

### 🏠 Páginas Principales

| Sección | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Inicio** | `/` | Página principal del sistema | Todos |
| **Login** | `/login/` | Inicio de sesión | Público |
| **Logout** | `/logout/` | Cerrar sesión | Autenticados |

### 💰 Sistema POS (Punto de Venta)

| Función | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Caja Registradora** | `/pos/` | Interfaz principal de caja | Todos |
| **Buscar Producto** | `/pos/search/` | Búsqueda de productos para venta | Todos |
| **Agregar al Carrito** | `/pos/cart/add/<id>/` | Añadir producto al carrito | Todos |
| **Remover del Carrito** | `/pos/cart/remove/<id>/` | Quitar producto del carrito | Todos |
| **Actualizar Cantidad** | `/pos/cart/update/<id>/` | Modificar cantidad en carrito | Todos |
| **Vaciar Carrito** | `/pos/cart/clear/` | Limpiar carrito completo | Todos |
| **Checkout** | `/pos/checkout/` | Procesar venta y completar transacción | Todos |

### 📦 Gestión de Productos

| Función | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Lista de Productos** | `/pos/products/` | Ver todos los productos con filtros | Todos |

### 🛒 Gestión de Ventas

| Función | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Historial de Ventas** | `/pos/sales/` | Ver todas las ventas realizadas | Todos |
| **Detalle de Venta** | `/pos/sales/<id>/` | Ver detalles de una venta específica | Todos |

### 📊 Gestión de Inventario

| Función | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Movimiento de Inventario** | `/pos/inventory/movement/` | Registrar entradas/salidas | Todos |

### 📑 Reportes

| Reporte | URL | Descripción | Exportación | Permisos |
|---------|-----|-------------|-------------|----------|
| **Reporte de Ventas** | `/pos/reports/sales/` | Reporte completo de ventas con filtros | PDF, Excel | Todos |
| **Reporte de Inventario** | `/pos/reports/inventory/` | Reporte de stock y productos | PDF, Excel | Todos |

**Filtros disponibles en Reporte de Ventas:**
- Rango de fechas
- Cajero
- Método de pago (Efectivo, Tarjeta, Transferencia)
- Estado (Completada, Cancelada, Pendiente)

**Filtros disponibles en Reporte de Inventario:**
- Categoría (EDT, EDP, EDC, Parfum, Splash, Accesorio)
- Género (Masculino, Femenino, Unisex)
- Marca
- Solo productos bajo stock
- Solo productos activos

**Formatos de exportación:**
- `?format=pdf` - Descarga en PDF
- `?format=excel` - Descarga en Excel

### 📈 Dashboard de Administrador

| Función | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Dashboard Principal** | `/pos/dashboard/` | Dashboard con gráficas interactivas | ADMIN/SUPERVISOR |

**APIs del Dashboard (JSON):**
- `/pos/dashboard/api/kpis/` - KPIs principales
- `/pos/dashboard/api/sales-trend/` - Tendencia de ventas
- `/pos/dashboard/api/sales-by-cashier/` - Ventas por cajero
- `/pos/dashboard/api/payment-methods/` - Distribución métodos de pago
- `/pos/dashboard/api/top-products/` - Top productos vendidos
- `/pos/dashboard/api/sales-by-category/` - Ventas por categoría
- `/pos/dashboard/api/sales-by-hour/` - Ventas por hora

**Características del Dashboard:**
- ⚡ Auto-actualización cada 60 segundos
- 📥 Exportación de gráficas a PNG
- 📱 Diseño responsive
- 🎛️ Filtros por fecha (hoy, últimos 7 días, mes actual, personalizado)

### ⚙️ Administración Django

| Función | URL | Descripción | Permisos |
|---------|-----|-------------|----------|
| **Admin Panel** | `/admin/` | Panel de administración de Django | Superuser/Staff |

---

## 🧭 Navegación Visual

### Barra de Navegación (Todas las páginas)

```
🏠 Inicio | 💰 Caja | 📦 Productos | 🛒 Ventas | 📊 Inventario |
📑 Reporte Ventas | 📋 Reporte Inventario | 📈 Dashboard* | ⚙️ Admin |
👤 Usuario | 🚪 Salir
```

_* Dashboard solo visible para ADMINISTRADOR y SUPERVISOR_

---

## 🔐 Niveles de Permisos

### Todos los usuarios autenticados:
- ✅ Caja registradora
- ✅ Productos
- ✅ Ventas
- ✅ Inventario
- ✅ Reportes (Ventas e Inventario)

### ADMINISTRADOR y SUPERVISOR:
- ✅ Todo lo anterior
- ✅ **Dashboard con gráficas**
- ✅ KPIs en tiempo real
- ✅ Análisis avanzado

### CAJERO:
- ✅ Caja registradora
- ✅ Productos
- ✅ Ventas
- ✅ Inventario
- ✅ Reportes
- ❌ Dashboard (sin acceso)

---

## 🚀 Acceso Rápido

### Para empezar a vender:
1. Ir a **💰 Caja** (`/pos/`)
2. Buscar productos
3. Agregar al carrito
4. Hacer **Checkout**

### Para ver reportes:
1. **Ventas**: `/pos/reports/sales/`
2. **Inventario**: `/pos/reports/inventory/`
3. Aplicar filtros
4. Exportar en PDF o Excel

### Para ver estadísticas (Admin/Supervisor):
1. Ir a **📈 Dashboard** (`/pos/dashboard/`)
2. Seleccionar rango de fechas
3. Ver gráficas interactivas
4. Exportar gráficas si es necesario

---

## 📞 Ayuda

Si tienes problemas accediendo al dashboard:
1. Verifica que tu usuario tenga rol ADMINISTRADOR o SUPERVISOR
2. Ve a `/admin/` → User profiles
3. Edita tu perfil y asigna el rol correcto

---

**Última actualización:** 2025-12-13
**Versión del sistema:** 1.0 (Dashboard + Reportes integrados)
