import os
import csv
import json
import logging
import requests
import subprocess
from datetime import datetime
from functools import wraps
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
import time
import sys
import io

load_dotenv()

# Forzar la codificación UTF-8 globalmente
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuración del log
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Configuración de Shopify
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOP_NAME = os.getenv("SHOP_NAME")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
REPORT_MAIL_ADDRESS = str(os.getenv("REPORT_MAIL_ADDRESS"))
REPORT_MAIL_APP_PASSWORD = os.getenv("REPORT_MAIL_APP_PASSWORD")
PC_SERVICE_PRODUCT_MARGIN = os.getenv("PC_SERVICE_PRODUCT_MARGIN")



# Decorador para limitar la tasa de solicitudes
def rate_limit(max_requests_per_minute):
    """
    Decorador para limitar el número de solicitudes por minuto.
    """
    interval = 60 / max_requests_per_minute
    last_call = [0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < interval:
                time.sleep(interval - elapsed)
            last_call[0] = time.time()
            return func(*args, **kwargs)

        return wrapper

    return decorator
############################################################################################################
def obtener_ruta_csv():
    """
    Obtiene la ruta absoluta del archivo CSV correspondiente a la fecha actual.
    """
    fecha_actual = datetime.now().strftime("%d_%m_%Y")
    carpeta_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), "../updates_products_csv"))
    archivo_csv = os.path.join(carpeta_csv, f"{fecha_actual}.csv")
    return archivo_csv
############################################################################################################
def leer_archivo_csv():
    """
    Lee el archivo CSV correspondiente a la fecha actual, ordena los productos por Id y devuelve una lista de productos.

    :return: Lista de diccionarios con los datos del producto, ordenados por Id.
    """
    archivo_csv = obtener_ruta_csv()
    productos = []

    if not os.path.exists(archivo_csv):
        logging.error(f"El archivo CSV del día actual ({archivo_csv}) no existe.")
        return productos

    try:
        with open(archivo_csv, mode="r", encoding="utf-8") as archivo:
            reader = csv.DictReader(archivo)
            for fila in reader:
                productos.append(fila)

        # Ordenar los productos por el campo 'Id' (conversión a entero para orden correcto)
        productos.sort(key=lambda x: int(x['ID']) if x['ID'].isdigit() else 0)

        logging.info(f"Se leyeron y ordenaron {len(productos)} productos del archivo CSV.")
    except Exception as e:
        logging.error(f"Error al leer el archivo CSV: {e}")

    return productos
############################################################################################################
def obtener_productos_shopify():
    """
    Obtiene todos los productos de Shopify, incluyendo precios, stock y manejando la paginación.

    :return: Lista de todos los productos obtenidos.
    """
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    # Consulta inicial para la primera página
    query_template = """
    query ($after: String) {
      products(first: 250, after: $after) {
        pageInfo {
          hasNextPage
        }
        edges {
          cursor
          node {
            id
            title
            variants(first: 10) {
              edges {
                node {
                    id
                    title
                    price
                    inventoryQuantity
                    inventoryItem {
                        id
                    }
                }
              }
            }
            metafields(namespace: "custom", first: 10) {
              edges {
                node {
                  key
                  value
                }
              }
            }
          }
        }
      }
    }
    """

    productos = {"data": {"products": {"edges": []}}}
    cursor = None
    has_next_page = True

    try:
        while has_next_page:
            variables = {"after": cursor}
            response = requests.post(url, headers=headers, json={"query": query_template, "variables": variables})

            # Log de la respuesta cruda
            logging.debug(f"Respuesta cruda de Shopify: {response.text}")

            # Verificar si la respuesta tiene un código de estado válido
            if response.status_code != 200:
                logging.error(f"Error al obtener productos de Shopify: {response.status_code} {response.text}")
                return None

            # Intentar parsear el JSON de la respuesta
            try:
                data = response.json()
            except ValueError:
                logging.error(f"La respuesta no contiene un JSON válido: {response.text}")
                return None

            # Validar la estructura esperada
            if "data" not in data or "products" not in data["data"]:
                logging.error(f"Estructura inesperada en la respuesta de Shopify: {response.json()}")
                return None

            # Agregar los productos a la lista
            productos["data"]["products"]["edges"].extend(data["data"]["products"]["edges"])

            # Actualizar `hasNextPage` y el cursor para la siguiente página
            page_info = data["data"]["products"]["pageInfo"]
            has_next_page = page_info["hasNextPage"]
            if has_next_page:
                cursor = productos["data"]["products"]["edges"][-1]["cursor"]

        logging.info(f"Se obtuvieron {len(productos['data']['products']['edges'])} productos de Shopify.")
        return productos

    except requests.RequestException as e:
        logging.error(f"Error de conexión al realizar la solicitud a Shopify: {e}")
        return None
############################################################################################################
def procesar_productos(productos_csv, productos_shopify):
    """
    Procesa los productos del archivo CSV y los compara con los productos de Shopify.
    Notifica por email los productos que fueron actualizados o pausados.

    :param productos_csv: Lista de productos del archivo CSV.
    :param productos_shopify: Lista de productos obtenidos desde Shopify.
    """
    # Crear un diccionario para buscar productos de Shopify por pc_service_id
    productos_shopify_dict = {}
    for producto_shopify in productos_shopify["data"]["products"]["edges"]:
        shopify_node = producto_shopify["node"]
        metafields = shopify_node.get("metafields", {}).get("edges", [])

        for metafield in metafields:
            if metafield["node"]["key"] == "pc_service_id":
                pc_service_id = metafield["node"]["value"]

                # Validar que existan variantes antes de acceder a los datos
                variants = shopify_node.get("variants", {}).get("edges", [])
                if variants:
                    variant_node = variants[0]["node"]
                    variant_id = variant_node.get("id")
                    inventory_item_id = variant_node.get("inventoryItem", {}).get("id")  # Extraer inventoryItem.id

                    productos_shopify_dict[pc_service_id] = {
                        "id": shopify_node["id"],
                        "title": shopify_node["title"],
                        "variant_id": variant_id,
                        "inventory_item_id": inventory_item_id,
                        "price": variant_node.get("price", "0.00"),
                        "stock": variant_node.get("inventoryQuantity", 0)
                    }

    # Inicializar reportes
    productos_pausados = []
    productos_actualizados = []

    # Procesar cada producto del CSV
    for producto_csv in productos_csv:
        pc_service_id = producto_csv.get("ID")

        if pc_service_id in productos_shopify_dict:
            logging.info(f"Producto con ID {pc_service_id} encontrado en Shopify.")
            producto_shopify = productos_shopify_dict[pc_service_id]

            # Comparar cambios
            cambios = []
            stock_csv = int(producto_csv.get("Stock", 0))
            precio_csv = float(producto_csv.get("Price", 0.0))
            if stock_csv == 0:
                logging.info(f"🛑 Pausando producto: {producto_shopify['title']}")
                productos_pausados.append(f"{producto_shopify['title']} (ID: {pc_service_id})")
            else:
                # Comparar precio
                if float(producto_shopify["price"]) != precio_csv:
                    cambios.append(f"Precio: {producto_shopify['price']} ➔ {precio_csv}")

                # Comparar stock
                if int(producto_shopify["stock"]) != stock_csv:
                    cambios.append(f"Stock: {producto_shopify['stock']} ➔ {stock_csv}")

                if cambios:
                    logging.info(f"🔄 Actualizando producto: {producto_shopify['title']}")
                    productos_actualizados.append(f"{producto_shopify['title']} (ID: {pc_service_id}) - Cambios: {', '.join(cambios)}")

            # Actualizar en Shopify
            actualizar_producto_en_shopify(producto_shopify, producto_csv)

    # Enviar email de reporte
    enviar_reporte_email(productos_pausados, productos_actualizados)

############################################################################################################
def enviar_reporte_email(productos_pausados, productos_actualizados):


    destinatario = "nicolasemaldonado@gmail.com,ni.camachosegovia@gmail.com"
    asunto = "📦 Reporte de Productos Actualizados en Shopify"

    # ✅ Asegurar que todo el contenido está en UTF-8
    cuerpo = u"<h2>Reporte de Actualización de Productos</h2>"

    if productos_pausados:
        cuerpo += u"<h3>🛑 Productos Pausados (Stock 0):</h3><ul>"
        for producto in productos_pausados:
            cuerpo += u"<li>{}</li>".format(producto)
        cuerpo += u"</ul>"
    else:
        cuerpo += u"<p>No se pausaron productos.</p>"

    if productos_actualizados:
        cuerpo += u"<h3>🔄 Productos Actualizados:</h3><ul>"
        for producto in productos_actualizados:
            cuerpo += u"<li>{}</li>".format(producto)
        cuerpo += u"</ul>"
    else:
        cuerpo += u"<p>No hubo actualizaciones de productos.</p>"

    try:

        if not isinstance(REPORT_MAIL_ADDRESS, str):
            raise ValueError(f"'REPORT_MAIL_ADDRESS' debe ser una cadena, pero es {type(REPORT_MAIL_ADDRESS).__name__}")
        if not isinstance(destinatario, str):
            raise ValueError(f"'destinatario' debe ser una cadena, pero es {type(destinatario).__name__}")
        if not isinstance(asunto, str):
            raise ValueError(f"'asunto' debe ser una cadena, pero es {type(asunto).__name__}")

        # ✅ Crear el mensaje asegurando UTF-8 en todas partes
        mensaje = MIMEMultipart()
        mensaje['From'] = Header(REPORT_MAIL_ADDRESS, 'utf-8')
        mensaje['To'] = Header(destinatario, 'utf-8')
        mensaje['Subject'] = Header(asunto, 'utf-8')

        # ✅ Adjuntar el cuerpo con codificación correcta
        mensaje.attach(MIMEText(cuerpo, 'html', 'utf-8'))

        # ✅ Configurar y enviar el correo
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.ehlo()
        servidor.starttls()
        servidor.login(REPORT_MAIL_ADDRESS, REPORT_MAIL_APP_PASSWORD)
        servidor.sendmail(REPORT_MAIL_ADDRESS, destinatario.split(","), mensaje.as_string())
        servidor.quit()

        logging.info("📧 Email de reporte enviado correctamente.")
    except Exception as e:
        logging.error(f"❌ Error al enviar el email de reporte: {e}")
############################################################################################################
def obtener_inventory_item_id(product_id):
    """
    Obtiene el `inventory_item_id` de un producto.
    
    :param product_id: ID del producto en Shopify.
    :return: ID del inventario o None.
    """
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{product_id}.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            product_data = response.json()
            return product_data["product"]["variants"][0]["inventory_item_id"]
        else:
            logging.error(f"Error al obtener inventory_item_id: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error inesperado al obtener inventory_item_id: {e}")
    
    return None
############################################################################################################
def obtener_location_id():
    """
    Obtiene el primer `location_id` activo para actualizar el inventario.
    
    :return: ID de la ubicación o None.
    """
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/locations.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            locations = response.json()
            return locations["locations"][0]["id"]  # Usar la primera ubicación activa
        else:
            logging.error(f"Error al obtener location_id: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error inesperado al obtener location_id: {e}")
    
    return None
############################################################################################################
def actualizar_stock_a_cero(inventory_item_id, location_id):
    """
    Establece el stock del producto a 0.
    
    :param inventory_item_id: ID del inventario del producto.
    :param location_id: ID de la ubicación.
    """
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/inventory_levels/set.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }
    data = {
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": 0
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            logging.info(f"✅ Stock actualizado a 0 para el inventory_item_id {inventory_item_id}.")
        else:
            logging.error(f"❌ Error al actualizar el stock: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"❌ Error inesperado al actualizar el stock: {e}")
############################################################################################################
def pausar_producto_en_shopify(product_id):
    """
    Pausa la publicación de un producto en Shopify cambiando su estado a "draft" y establece el stock en 0.

    :param product_id: El ID del producto en Shopify en formato GraphQL (gid://shopify/Product/{id}).
    """
    # Extraer el identificador numérico del ID de GraphQL
    numeric_id = product_id.split("/")[-1]

    # 1️⃣ Cambiar el estado del producto a "draft"
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{numeric_id}.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }
    data = {
        "product": {
            "id": numeric_id,
            "status": "draft"
        }
    }

    try:
        response = requests.put(url, json=data, headers=headers)
        if response.status_code == 200:
            logging.info(f"✅ Producto {numeric_id} pausado (status: draft).")
        else:
            logging.error(f"❌ Error al pausar el producto {numeric_id}: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"❌ Error inesperado al pausar el producto {numeric_id}: {e}")

    # 2️⃣ Establecer el stock en 0
    inventory_item_id = obtener_inventory_item_id(numeric_id)
    location_id = obtener_location_id()

    if inventory_item_id and location_id:
        actualizar_stock_a_cero(inventory_item_id, location_id)
    else:
        logging.error(f"❌ No se pudo obtener inventory_item_id o location_id para el producto {numeric_id}")
############################################################################################################
def obtener_locations():
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/locations.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            locations = response.json()
            logging.info(f"Ubicaciones obtenidas: {locations}")
            return locations
        else:
            logging.error(f"Error al obtener ubicaciones: {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"Error inesperado al obtener ubicaciones: {e}")

LOCATION_ID = obtener_locations()
############################################################################################################
def actualizar_producto_en_shopify(producto_shopify, producto_csv):
    """
    Actualiza el stock y el precio de un producto en Shopify.

    :param producto_shopify: Diccionario con los datos del producto en Shopify.
    :param producto_csv: Diccionario con los datos del producto desde el CSV.
    """
    try:
        # Extraer datos clave
        product_id_global = producto_shopify["id"]
        variant_id_global = producto_shopify.get("variant_id")
        inventory_item_id = producto_shopify.get("inventory_item_id", "")
        if not inventory_item_id:
            raise ValueError(f"⚠️ 'inventory_item_id' no es válido para el producto '{producto_shopify['title']}'")
        inventory_item_id_numeric = inventory_item_id.split("/")[-1]

        # Extraer datos del CSV
        stock_csv = int(producto_csv.get("Stock", 0))
        precio_csv = float(producto_csv.get("Price", 0.0))

        # Calcular el precio con el margen
        price_with_margin = round(precio_csv * float(PC_SERVICE_PRODUCT_MARGIN), 2)

        # Actualizar precio
        product_url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{product_id_global.split('/')[-1]}.json"
        product_payload = {
            "product": {
                "variants": [
                    {
                        "id": variant_id_global.split("/")[-1],
                        "price": str(price_with_margin),
                        "cost": str(precio_csv)
                    }
                ]
            }
        }
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        }
        response = requests.put(product_url, headers=headers, json=product_payload)
        if response.status_code == 200:
            logging.info(f"✅ Producto actualizado correctamente en Shopify: {producto_shopify['title']}")
        else:
            logging.error(f"❌ Error al actualizar el producto en Shopify: {response.status_code} {response.text}")

        # Actualizar inventario
        inventory_url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/inventory_levels/set.json"
        inventory_payload = {
            "location_id": 70192627918,
            "inventory_item_id": inventory_item_id_numeric,
            "available": stock_csv
        }
        logging.debug(f"Payload enviado para inventario: {json.dumps(inventory_payload, indent=2)}")
        inventory_response = requests.post(inventory_url, headers=headers, json=inventory_payload)
        if inventory_response.status_code == 200:
            logging.info(f"✅ Inventario actualizado correctamente en Shopify: {producto_shopify['title']}")
        else:
            logging.error(f"❌ Error al actualizar el inventario en Shopify: {inventory_response.status_code} {inventory_response.text}")

    except Exception as e:
        logging.error(f"❌ Error inesperado al actualizar el producto: {e}")
############################################################################################################
def procesar_archivo_csv():
    """
    Procesa el archivo CSV y compara los productos con Shopify.
    """
    productos_csv = leer_archivo_csv()
    if not productos_csv:
        return

    productos_shopify = obtener_productos_shopify()
    procesar_productos(productos_csv, productos_shopify)
############################################################################################################
# Ejecutar el script
if __name__ == "__main__":
    procesar_archivo_csv()
