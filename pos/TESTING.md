# Guía de Pruebas - Sistema POS RubiPerfumeria

## Resumen

Este documento describe las pruebas implementadas para el sistema POS de RubiPerfumeria.

## Tipos de Pruebas

### 1. Pruebas Unitarias (`pos/tests.py`)

Pruebas unitarias completas para todos los modelos del sistema POS:

- **ProductModelTest** (13 pruebas)
  - Creación y validación de productos
  - Propiedades: `disponible`, `requiere_reabastecimiento`, `valor_inventario`
  - Método `__str__` con y sin volumen
  - Validaciones de precio y stock

- **SalesModelTest** (12 pruebas)
  - Creación de ventas
  - Generación automática de número de ticket
  - Formato y numeración incremental de tickets
  - Propiedades: `subtotal`, `cantidad_productos`
  - Validaciones de total y descuento

- **SaleDetailsModelTest** (6 pruebas)
  - Creación de detalles de venta
  - Cálculo automático de subtotales
  - Reducción de stock al crear detalles
  - Validación de stock insuficiente

- **InventoryModelTest** (4 pruebas)
  - Movimientos de inventario (entrada, salida, devolución)
  - Validación de stock negativo
  - Actualización automática de stock

- **UserProfileModelTest** (4 pruebas)
  - Creación y gestión de perfiles de usuario
  - Propiedades y métodos del perfil

**Total: 39 pruebas unitarias**

### 2. Pruebas de Integración con Selenium (`pos/test_selenium.py`)

Pruebas end-to-end que simulan la interacción del usuario con el sistema:

- **AdminSeleniumTests**
  - Login al panel de administración
  - Crear productos desde el admin
  - Ver lista de productos
  - Buscar productos
  - Crear ventas

- **ProductWorkflowSeleniumTests**
  - Ciclo de vida completo de un producto (crear, editar, verificar)

**Nota:** Las pruebas de Selenium requieren que Chrome o Chromium esté instalado en el sistema. Si no está disponible, estas pruebas se saltarán automáticamente.

## Cómo Ejecutar las Pruebas

### Activar el entorno virtual

```bash
source venv/bin/activate
```

### Ejecutar todas las pruebas unitarias

```bash
python manage.py test pos.tests --verbosity=2
```

### Ejecutar una clase de pruebas específica

```bash
# Solo pruebas de Product
python manage.py test pos.tests.ProductModelTest --verbosity=2

# Solo pruebas de Sales
python manage.py test pos.tests.SalesModelTest --verbosity=2

# Solo pruebas de SaleDetails
python manage.py test pos.tests.SaleDetailsModelTest --verbosity=2
```

### Ejecutar una prueba específica

```bash
python manage.py test pos.tests.ProductModelTest.test_crear_producto --verbosity=2
```

### Ejecutar pruebas de Selenium

**Prerrequisito:** Instalar Chrome/Chromium en tu sistema.

```bash
# Instalar Chrome en Ubuntu/Debian
sudo apt-get update
sudo apt-get install chromium-browser

# O instalar Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get -f install
```

Luego ejecutar:

```bash
python manage.py test pos.test_selenium --verbosity=2
```

### Ejecutar todas las pruebas (unitarias + Selenium)

```bash
python manage.py test pos --verbosity=2
```

## Cobertura de Pruebas

Las pruebas cubren:

1. ✅ Creación y validación de todos los modelos
2. ✅ Propiedades y métodos calculados
3. ✅ Validaciones de datos (precios, stock, descuentos)
4. ✅ Generación automática de números de ticket
5. ✅ Gestión de inventario (entradas, salidas, devoluciones)
6. ✅ Reducción automática de stock en ventas
7. ✅ Validación de stock insuficiente
8. ✅ Interfaz de administración (con Selenium)
9. ✅ Flujos de trabajo completos (con Selenium)

## Dependencias de Testing

Las dependencias de testing ya están instaladas:

```bash
selenium==4.39.0
webdriver-manager==4.0.2
```

## Resultados Esperados

Todas las pruebas unitarias deben pasar:

```
Ran 39 tests in ~19s
OK
```

## Notas Importantes

1. **Base de datos de pruebas**: Django crea automáticamente una base de datos de prueba en memoria que se destruye después de cada ejecución.

2. **Aislamiento**: Cada prueba se ejecuta de forma aislada con su propia transacción que se revierte al finalizar.

3. **Selenium en modo headless**: Las pruebas de Selenium se ejecutan en modo headless (sin interfaz gráfica) para mayor velocidad y compatibilidad con CI/CD.

4. **Skip automático**: Si Chrome no está disponible, las pruebas de Selenium se saltarán automáticamente sin causar errores.

## Integración Continua

Para integrar estas pruebas en un pipeline de CI/CD:

```yaml
# Ejemplo para GitHub Actions
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    - name: Install Chrome
      run: |
        sudo apt-get update
        sudo apt-get install chromium-browser
    - name: Run tests
      run: |
        python manage.py test pos --verbosity=2
```

## Próximos Pasos

Para expandir la cobertura de pruebas, considera:

1. Añadir pruebas para las vistas (cuando se implementen)
2. Pruebas de rendimiento para operaciones con grandes volúmenes de datos
3. Pruebas de concurrencia para ventas simultáneas
4. Pruebas de APIs (cuando se implementen endpoints REST)
5. Cobertura de código con `coverage.py`

## Contacto

Para preguntas o problemas con las pruebas, contacta al equipo de desarrollo.
