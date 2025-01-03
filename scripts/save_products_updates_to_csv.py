import os
import requests
import csv
import logging
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL")
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")

SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOP_NAME = os.getenv("SHOP_NAME")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")

# Paso 1: Función para autenticarse y obtener el token (si es necesario)
def obtener_token():
    logging.info("Iniciando autenticación para obtener el token.")
    url_auth = f"{BASE_URL}/auth/login"
    data_auth = {'username': API_USERNAME, 'password': API_PASSWORD}
    
    response = requests.post(url_auth, json=data_auth)
    if response.status_code == 200:
        logging.info("Autenticación exitosa. Token obtenido.")
        return response.json()['token']
    else:
        logging.error(f"Error en autenticación: {response.status_code}")
        raise Exception(f"Error en autenticación: {response.status_code}")

# Paso 2: Función para consumir el servicio web y obtener los productos actualizados
def obtener_productos_actualizados(token, desde, hasta):
    logging.info(f"Obteniendo productos actualizados desde {desde} hasta {hasta}.")
    url_actualizaciones = f'{BASE_URL}/products/bydate?from={desde}&to={hasta}'
    headers = {'Authorization': f'Bearer {token}'}
    
    response = requests.get(url_actualizaciones, headers=headers)
    if response.status_code == 200:
        logging.info(f"Productos obtenidos correctamente. Total: {len(response.json())}.")
        return response.json()
    else:
        logging.error(f"Error al obtener productos: {response.status_code}")
        raise Exception(f"Error al obtener productos: {response.status_code}")

# Paso 3: Función para descargar y guardar una imagen
def guardar_imagen(url_imagen, carpeta_producto, product_id):
    logging.info(f"Descargando imagen: {url_imagen}")
    response = requests.get(url_imagen)
    
    if response.status_code == 200:
        nombre_original = os.path.basename(url_imagen)
        
        if 'ICO' in nombre_original.upper():
            nombre_archivo = nombre_original
        else:
            existing_images = [f for f in os.listdir(carpeta_producto) if f.startswith(f"{product_id}_")]
            image_number = len(existing_images) + 1
            nombre_archivo = f"{product_id}_{image_number}.jpg"
        
        ruta_imagen = os.path.join(carpeta_producto, nombre_archivo)
        with open(ruta_imagen, 'wb') as file:
            file.write(response.content)
        logging.info(f"Imagen guardada: {ruta_imagen}")
    else:
        logging.warning(f"Error al descargar imagen: {url_imagen}")

# Paso 4: Función para limpiar los campos eliminando los saltos de línea
def limpiar_texto(texto):
    if texto:
        return texto.replace('\n', ' ').replace('\r', ' ').strip()
    return 'N/A'

# Paso 5: Función para concatenar categorías (principal e hijas)
def obtener_categoria(producto):
    if 'categories' in producto and len(producto['categories']) > 0:
        categoria_principal = producto['categories'][0]['title']
        categorias_hijas = [child['title'] for child in producto['categories'][0].get('childs', [])]
        todas_categorias = [categoria_principal] + categorias_hijas
        return " > ".join(todas_categorias)
    return 'Sin categoría'

# Paso 6: Función principal para procesar los productos y guardar el CSV e imágenes
def procesar_productos(from_date=None, to_date=None, file_name=None):
    logging.info("Iniciando procesamiento de productos.")
    token = obtener_token()

    if not from_date or not to_date:
        ayer = datetime.now() - timedelta(days=1)
        from_date = ayer.strftime('%Y%m%d') + '000000'
        to_date = ayer.strftime('%Y%m%d') + '235959'

    productos = obtener_productos_actualizados(token, from_date, to_date)

    carpeta_principal = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'updates_products_csv')
    os.makedirs(carpeta_principal, exist_ok=True)
    if not file_name:
        file_name = f"{datetime.now().strftime('%d_%m_%Y')}.csv"

    ruta_archivo_csv = os.path.join(carpeta_principal, file_name)

    with open(ruta_archivo_csv, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['ID', 'SKU', 'Title', 'Brand', 'Stock', 'Currency', 'Price', 'Changes', 'Barcode', 'Category', 'Description', 'Body', 'Image_URLs'])

        for producto in productos:

            try:
                procesar_producto_shopify(producto)
            except Exception as e:
                logging.error(f"Error procesando el producto {producto['pc_service_id']}: {e}")
        
            stock = producto['availability']['stock']
            #if stock == 0:
            #    logging.info(f"Producto {producto['id']} omitido por stock 0.")
            #    continue

            cambios = producto['extraData'].get('changes', [])
            #if cambios == ['stock'] and stock > 1:
            #    logging.info(f"Producto {producto['id']} omitido: único cambio es 'stock'.")
            #    continue

            product_id = producto['id']
            sku = producto.get('sku', 'N/A')
            title = limpiar_texto(producto['title'])
            brand = producto['extraData'].get('brand', 'N/A')
            currency = producto['price']['currency']
            price = producto['price']['price']
            barcode = producto['extraData'].get('barcode', 'N/A')
            category = limpiar_texto(obtener_categoria(producto))
            description = limpiar_texto(producto['description'])
            body = limpiar_texto(producto.get('body', 'N/A'))
            changes = ','.join(cambios)

            image_urls = []
            for image in producto['images']:
                for variation in image['variations']:
                    url_imagen = variation['url']
                    image_urls.append(url_imagen)

            urls_concatenadas = '"' + ', '.join(image_urls) + '"'
            writer.writerow([product_id, sku, title, brand, stock, currency, price, changes, barcode, category, description, body, urls_concatenadas])

    logging.info(f"Archivo CSV guardado correctamente en: {ruta_archivo_csv}")


def procesar_producto_shopify(producto):
    """
    Procesa un producto individual. Verifica si existe, actualiza datos o pausa la publicación según sea necesario.

    :param producto: Diccionario con los datos del producto.
    """
    pc_service_id = producto.get('id')
    if not pc_service_id:
        logging.warning("Producto sin 'pc_service_id'. Omitido.")
        return

    shopify_product = buscar_producto_en_shopify(pc_service_id)

    if not shopify_product:
        logging.info(f"Producto con 'pc_service_id' {pc_service_id} no encontrado en Shopify. Omitido.")
        return

    if producto.get('stock', 0) == 0:
        pausar_publicacion(shopify_product)
    else:
        actualizar_producto(shopify_product, producto)


def buscar_producto_en_shopify(pc_service_id):
    """
    Busca un producto en Shopify por 'pc_service_id'.

    :param pc_service_id: ID del servicio en el sistema para buscar en Shopify.
    :return: Diccionario con los datos del producto en Shopify, o None si no se encuentra.
    """
    logging.info(f"Buscando producto en Shopify con 'pc_service_id': {pc_service_id}")
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json?fields=id,title&metafield[namespace]=custom&metafield[key]=pc_service_id&metafield[value]={pc_service_id}"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logging.error(f"Error al buscar producto en Shopify: {response.status_code} {response.text}")
        return None

    products = response.json().get("products", [])
    return products[0] if products else None

def actualizar_producto(shopify_product, producto):
    """
    Actualiza los datos del producto en Shopify.

    :param shopify_product: Diccionario con los datos actuales del producto en Shopify.
    :param producto: Diccionario con los nuevos datos del producto.
    """
    logging.info(f"Actualizando producto en Shopify: {shopify_product['id']}")
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{shopify_product['id']}.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN}
    data = {
        "product": {
            "id": shopify_product['id'],
            "title": producto.get('title'),
            "variants": [{
                "inventory_quantity": producto.get('stock', 0),
                "price": producto.get('price', 0.0)
            }]
        }
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code != 200:
        logging.error(f"Error al actualizar producto en Shopify: {response.status_code} {response.text}")
    else:
        logging.info(f"Producto actualizado exitosamente: {shopify_product['id']}")

def pausar_publicacion(shopify_product):
    """
    Pausa la publicación del producto en Shopify.

    :param shopify_product: Diccionario con los datos actuales del producto en Shopify.
    """
    logging.info(f"Pausando publicación del producto en Shopify: {shopify_product['id']}")
    url = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{shopify_product['id']}.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN}
    data = {
        "product": {
            "id": shopify_product['id'],
            "status": "draft"
        }
    }

    response = requests.put(url, json=data, headers=headers)
    if response.status_code != 200:
        logging.error(f"Error al pausar publicación en Shopify: {response.status_code} {response.text}")
    else:
        logging.info(f"Producto pausado exitosamente: {shopify_product['id']}")


# Paso 7: Ejecutar la función principal para iniciar el proceso
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Procesar productos entre fechas específicas.")
    parser.add_argument("--from_date", type=str, help="Fecha de inicio en formato YYYYMMDDHHMMSS")
    parser.add_argument("--to_date", type=str, help="Fecha de fin en formato YYYYMMDDHHMMSS")
    parser.add_argument("--file_name", type=str, help="Nombre del archivo CSV")
    args = parser.parse_args()

    procesar_productos(from_date=args.from_date, to_date=args.to_date, file_name=args.file_name)
