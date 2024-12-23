from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import requests
import os
import logging
import time

# Cargar configuraciones
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas

BASE_URL = os.getenv("API_BASE_URL")
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOP_NAME = os.getenv("SHOP_NAME")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")

# Variables globales para gestionar el token
cached_token = None
token_expiry = 0
api_token = None

logger = logging.getLogger(__name__)

def authenticate():
    try:
        if not all([BASE_URL, API_USERNAME, API_PASSWORD]):
            raise Exception("Faltan credenciales o configuración de la API.")

        url = f"{BASE_URL}/auth/login"
        payload = {"username": API_USERNAME, "password": API_PASSWORD}

        logger.info("Intentando autenticar. URL: %s, Método: POST", url)
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            data = response.json()
            token = data.get("token")

            if not token:
                raise Exception("No se encontró el token en la respuesta.")
            
            logger.info("Autenticación exitosa. Token obtenido.")
            return token

        else:
            logger.error("Error al autenticar. Status: %s, Respuesta: %s", response.status_code, response.text)
            raise Exception(f"Error al autenticar: {response.status_code} - {response.text}")

    except requests.exceptions.RequestException as e:
        logger.error("Error de red al autenticar: %s", str(e))
        raise Exception("Error de red al autenticar.") from e

    except Exception as e:
        logger.error("Error inesperado durante la autenticación: %s", str(e))
        raise


def get_valid_token():
    global api_token
    if not api_token:
        api_token = authenticate()
    return api_token


@app.route('/api/categories/', defaults={'category_id': None, 'subcategory_id': None}, methods=['GET'])
@app.route('/api/categories/<int:category_id>', defaults={'subcategory_id': None}, methods=['GET'])
@app.route('/api/categories/<int:category_id>/<int:subcategory_id>', methods=['GET'])
def get_categories(category_id, subcategory_id):
    try:
        token = get_valid_token()
        url = f"{BASE_URL}/categories/"

        # Construir la URL según los parámetros proporcionados
        if category_id:
            url += f"/{category_id}"
        if subcategory_id:
            url += f"/{subcategory_id}/products"

        logger.info("url %s", url)
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers)

        logger.info("Respuesta del servidor: %s", response.json())

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):  # Si la respuesta es una lista
                logger.info("Respuesta de categorías obtenida correctamente (lista).")
                return jsonify(data)
            elif isinstance(data, dict):  # Si la respuesta es un diccionario
                logger.info("Respuesta de categorías obtenida correctamente (diccionario).")
                return jsonify(data)
            else:
                logger.error("Formato inesperado de la respuesta: %s", data)
                return handle_error("Formato inesperado de la respuesta.", 500)
        else:
            logger.error("Error en la solicitud: %s", response.text)
            response_data = response.json()
            # Manejar si la respuesta es lista o diccionario
            if isinstance(response_data, dict):
                return handle_error(response_data.get("message", "Error desconocido"), response.status_code)
            else:
                return handle_error("Error desconocido en la respuesta del servidor.", response.status_code)

    except Exception as e:
        logger.error("Error en /api/categories: %s", str(e))
        return handle_error(str(e), 500)


@app.route('/api/product/<int:product_id>', methods=['GET'])
def get_product_details(product_id):
    try:
        if product_id <= 0:
            return handle_error("El ID del producto debe ser un número positivo", 400)

        token = get_valid_token()
        url = f"{BASE_URL}/products/{product_id}"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return handle_error(response.json().get("message", "Error desconocido"), response.status_code)
    except Exception as e:
        logger.error("Error en /api/product: %s", str(e))
        return handle_error(str(e))
    
    
@app.route('/api/shopify/create_product', methods=['POST'])
def create_product_in_shopify():
    try:
      
        SHOPIFY_API_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"

        data = request.json
        if not data:
            return handle_error("No se proporcionaron datos del producto", 400)

        # Crear el payload para Shopify
        shopify_payload = {
            "product": {
                "title": data.get("title"),
                "body_html": data.get("description"),
                "vendor": data.get("vendor"),
                "product_type": data.get("product_type"),
                "tags": data.get("tags", []),
                "variants": data.get("variants", [])
            }
        }

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
        }

        response = requests.post(SHOPIFY_API_URL, json=shopify_payload, headers=headers)

        if response.status_code == 201:
            logger.info("Producto creado exitosamente en Shopify.")
            return jsonify(response.json()), 201
        else:
            logger.error("Error al crear el producto en Shopify. Respuesta: %s", response.text)
            return handle_error(response.json().get("errors", "Error desconocido al crear el producto"), response.status_code)

    except Exception as e:
        logger.error("Error en /api/shopify/create_product: %s", str(e))
        return handle_error(str(e))


def handle_error(message, status_code=500):
    return jsonify({"error": message}), status_code

if __name__ == '__main__':
    try:
        api_token = authenticate()
        logger.info("Servidor 2 iniciado y autenticado.")
        app.run(host='0.0.0.0', port=5001, debug=True)
    except Exception as e:
        logger.error("Error al iniciar el servidor: %s", str(e))
