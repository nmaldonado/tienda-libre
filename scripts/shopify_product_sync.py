import os
import csv
import logging
import requests
from datetime import datetime
from functools import wraps
import time

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


def obtener_ruta_csv():
    """
    Obtiene la ruta absoluta del archivo CSV correspondiente a la fecha actual.
    """
    fecha_actual = datetime.now().strftime("%d_%m_%Y")
    carpeta_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), "../updates_products_csv"))
    archivo_csv = os.path.join(carpeta_csv, f"{fecha_actual}.csv")
    return archivo_csv


# Leer el archivo CSV
def leer_archivo_csv():
    """
    Lee el archivo CSV correspondiente a la fecha actual y devuelve una lista de productos.

    :return: Lista de diccionarios con los datos del producto.
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
        logging.info(f"Se leyeron {len(productos)} productos del archivo CSV.")
    except Exception as e:
        logging.error(f"Error al leer el archivo CSV: {e}")

    return productos


# Obtener productos de Shopify
def obtener_productos_shopify():
    """
    Obtiene todos los productos de Shopify y registra la respuesta sin procesarla.

    :return: Respuesta cruda de Shopify (opcionalmente None en caso de error).
    """
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    query = """
    query {
      products(first: 250) {
        edges {
          node {
            id
            title
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

    try:
        response = requests.post(url, headers=headers, json={"query": query})

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

        return data

    except requests.RequestException as e:
        logging.error(f"Error de conexión al realizar la solicitud a Shopify: {e}")
        return None



# Procesar productos
def procesar_productos(productos_csv, productos_shopify):
    """
    Procesa los productos del archivo CSV y los compara con los productos de Shopify.

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
                productos_shopify_dict[pc_service_id] = {
                    "id": shopify_node["id"],
                    "title": shopify_node["title"]
                }

    # Procesar cada producto del CSV
    for producto_csv in productos_csv:
        pc_service_id = producto_csv.get("ID")

        if pc_service_id in productos_shopify_dict:
            # log Producto encontrado en Shopify
            logging.info(f"Producto con ID {pc_service_id} encontrado en Shopify.")
            producto_shopify = productos_shopify_dict[pc_service_id]
            stock_csv = int(producto_csv.get("Stock", 0))

            if stock_csv == 0:
                # Pausar publicación si el stock es 0
                logging.info(f"Pausando producto en Shopify: {producto_shopify['title']}")
                pausar_producto_en_shopify(producto_shopify["id"])
            else:
                # Actualizar producto en Shopify
                logging.info(f"Actualizando producto en Shopify: {producto_shopify['title']}")
                #actualizar_producto_en_shopify(
                #    producto_id=producto_shopify["id"],
                #    stock=stock_csv,
                #    price=float(producto_csv.get("Price", 0.0)),
                #    title=producto_csv.get("Title", ""),
                #)
        else:
            logging.info(f"Producto con ID {pc_service_id} no encontrado en Shopify. No se realiza ninguna acción.")




def pausar_producto_en_shopify(product_id):
    """
    Pausa la publicación de un producto en Shopify cambiando su estado a "draft".

    :param product_id: El ID del producto en Shopify en formato GraphQL (gid://shopify/Product/{id}).
    """
    # Extraer el identificador numérico del ID de GraphQL
    numeric_id = product_id.split("/")[-1]

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
        response = requests.put(url, headers=headers, json=data)

        # Verificar si la respuesta tiene un código de estado válido
        if response.status_code == 200:
            logging.info(f"Producto {numeric_id} pausado exitosamente en Shopify.")
        else:
            logging.error(f"Error al pausar producto {numeric_id} en Shopify: {response.status_code} {response.text}")

    except requests.RequestException as e:
        logging.error(f"Error de conexión al intentar pausar producto {numeric_id}: {e}")



def actualizar_producto_en_shopify(producto_shopify, producto_csv):
    """
    Actualiza el producto en Shopify con los datos del archivo CSV.

    :param producto_shopify: Producto existente en Shopify.
    :param producto_csv: Producto del archivo CSV.
    """
    logging.info(f"Actualizando producto: {producto_shopify['id']} con datos del CSV.")
    # Implementar la lógica de actualización aquí

# Procesar archivo CSV
def procesar_archivo_csv():
    """
    Procesa el archivo CSV y compara los productos con Shopify.
    """
    productos_csv = leer_archivo_csv()
    if not productos_csv:
        return

    productos_shopify = obtener_productos_shopify()
    procesar_productos(productos_csv, productos_shopify)

# Ejecutar el script
if __name__ == "__main__":
    procesar_archivo_csv()
