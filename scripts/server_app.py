from flask import Flask, request, jsonify, make_response,redirect
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
import requests
import os
import logging
import time
import sys
import pandas as pd
import datetime



# Cargar configuraciones
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)




BASE_URL = os.getenv("API_BASE_URL")
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOP_NAME = os.getenv("SHOP_NAME")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Variables globales para el token y su tiempo de generación
api_token = None
token_generated_time = None
TOKEN_VALIDITY_PERIOD = 600  # Validez del token: 10 minutos
logger = logging.getLogger(__name__)

app = Flask(__name__)


CORS(app)

@app.route('/login', methods=['POST'])
def login():
    # Manejo de solicitud POST
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        logger.info("Login exitoso para el usuario %s", username)
        return jsonify({"message": "Login exitoso"}), 200

    return jsonify({"message": "Usuario o contraseña incorrectos"}), 401



    
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({"message": f"Bienvenido, {current_user}. Acceso permitido."}), 200
    

def authenticateOnPCService():
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

def is_token_valid():
    """Comprueba si el token actual es válido."""
    global token_generated_time
    if not api_token or not token_generated_time:
        return False
    return time.time() < (token_generated_time + TOKEN_VALIDITY_PERIOD)

def get_valid_token():
    """Obtiene un token válido, renovándolo si es necesario."""
    global api_token, token_generated_time
    if not is_token_valid():
        logger.info("El token no es válido o ha expirado. Autenticando de nuevo.")
        try:
            api_token = authenticateOnPCService()
            token_generated_time = time.time()  # Actualizar el tiempo de generación del token
        except Exception as e:
            logger.error("Error al obtener un nuevo token: %s", str(e))
            raise
    else:
        logger.info("Token válido encontrado, no es necesario renovarlo.")
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
        
        cost_per_item = data.get("price", {}).get("price", 0)
        price_with_margin = round(cost_per_item * 1.18, 2)

        logger.info("Price: %s", data.get("price", {}))
        logger.info("Price with margin: %s", price_with_margin)


        # Crear el payload para Shopify con todos los campos disponibles    
        shopify_payload = {
            "product": {
                "title": data.get("title"),
                "body_html": data.get("body"),
                "vendor": data.get("extraData", {}).get("brand"),
                "product_type": data.get("type"),
                "tags": data.get("tags", []),
                "variants": [
                    {
                        "price": price_with_margin,  # Precio con margen
                        "cost": cost_per_item,  # Cost per item (costo base)
                        "sku": data.get("price", {}).get("sku"),
                        "inventory_quantity": data.get("availability", {}).get("stock", 0),
                        "barcode": data.get("extraData", {}).get("barcode")
                    }
                ],
                "images": [
                    {"src": variation.get("url")}
                    for image in data.get("images", [])
                    for variation in image.get("variations", [])
                ]
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

# Directorio donde se encuentran los archivos CSV
CSV_DIRECTORY = "../updates_products_csv"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@app.route('/data', methods=['GET'])
def serve_csv_as_json():
    # Obtener la fecha actual o usar el parámetro `date`
    file_date = request.args.get('date', pd.Timestamp.now().strftime('%d_%m_%Y'))
    file_name = f"{file_date}.csv"
    file_path = os.path.join(CSV_DIRECTORY, file_name)

    # Verificar si el archivo existe
    if not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    try:
        # Leer el archivo CSV y manejar valores NaN
        data = pd.read_csv(file_path)
        data = data.fillna('')  # Reemplazar NaN con cadenas vacías

        # Convertir el DataFrame a JSON y devolverlo
        return jsonify(data.to_dict(orient='records'))
    except Exception as e:
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500

def handle_error(message, status_code=500):
    return jsonify({"error": message}), status_code

if __name__ == '__main__':
    try:
        api_token = authenticateOnPCService()
        logger.info("Servidor api_server iniciado y autenticado.")
        app.run(host='0.0.0.0', port=5001, debug=True)
    except Exception as e:
        logger.error("Error al iniciar el servidor: %s", str(e))
