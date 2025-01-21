from flask import Flask, request, jsonify, make_response,redirect
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
from pathlib import Path
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
PC_SERVICE_PRODUCT_MARGIN = os.getenv("PC_SERVICE_PRODUCT_MARGIN")

# Variables globales para el token y su tiempo de generación
api_token = None
token_generated_time = None
TOKEN_VALIDITY_PERIOD = 600  # Validez del token: 10 minutos
logger = logging.getLogger(__name__)

app = Flask(__name__)


CORS(app)


############################################################################################################
@app.route('/api/login', methods=['POST'])
def login():
    # Manejo de solicitud POST
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        logger.info("Login exitoso para el usuario %s", username)
        return jsonify({"message": "Login exitoso"}), 200

    return jsonify({"message": "Usuario o contraseña incorrectos"}), 401


############################################################################################################ 
@app.route('/api/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({"message": f"Bienvenido, {current_user}. Acceso permitido."}), 200
    
############################################################################################################
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

############################################################################################################
def is_token_valid():
    """Comprueba si el token actual es válido."""
    global token_generated_time
    if not api_token or not token_generated_time:
        return False
    return time.time() < (token_generated_time + TOKEN_VALIDITY_PERIOD)

############################################################################################################
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

############################################################################################################
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

############################################################################################################
@app.route('/api/products', methods=['POST'])
def get_product_details():
    try:
        data = request.json
        product_ids = data.get("product_ids", [])

        if not isinstance(product_ids, list) or len(product_ids) == 0:
            return handle_error("Debes proporcionar una lista de IDs de productos.", 400)

        # Limitar la cantidad de productos a procesar
        MAX_PRODUCTS = 10
        if len(product_ids) > MAX_PRODUCTS:
            return handle_error(f"El límite máximo de productos a consultar es {MAX_PRODUCTS}.", 400)

        token = get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}

        results = []

        for product_id in product_ids:
            try:
                # Convertir product_id a entero para evitar problemas de tipo
                product_id = int(product_id)

                if product_id <= 0:
                    results.append({"product_id": product_id, "status": "error", "message": "El ID del producto debe ser un número positivo."})
                    continue

                url = f"{BASE_URL}/products/{product_id}"
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    results.append({"product_id": product_id, "status": "success", "data": response.json()})
                else:
                    error_message = response.json().get("message", "Error desconocido")
                    results.append({"product_id": product_id, "status": "error", "message": error_message})

            except ValueError:
                results.append({"product_id": product_id, "status": "error", "message": "El ID del producto debe ser un número válido."})
            except Exception as e:
                logger.error(f"Error al consultar producto con ID {product_id}: {e}")
                results.append({"product_id": product_id, "status": "error", "message": str(e)})

        return jsonify({"results": results}), 200

    except Exception as e:
        logger.error("Error en /api/products: %s", str(e))
        return handle_error(str(e))


############################################################################################################
@app.route('/api/shopify/create_products', methods=['POST'])
def create_products_in_shopify():
    try:
        SHOPIFY_API_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json"


        data = request.json
        #log data
        logger.info(f"Data recibida:  {data}")

        # Obtener detalles de los productos
        product_details_response = get_product_details_internal(data)

        if product_details_response[1] != 200:
            logger.error("Error al obtener detalles de los productos.")
            return handle_error("Error al obtener detalles de los productos.", product_details_response[1])

        product_details = product_details_response[0].get("results", [])
        results = []

        for product in product_details:
            logger.info(f"Procesando producto: {product}")
            pc_service_product_id = product.get("product_id")

            if product.get("status") != "success":
                logger.error(f"Error en detalles del producto con ID {pc_service_product_id}: {product.get('message')}")
                results.append({"pc_service_product_id": pc_service_product_id, "status": "error", "message": product.get("message")})
                continue


            product_data = product.get("data")

            
            cost_per_item = product_data.get("price", {}).get("price", 0)
            price_with_margin = round(cost_per_item * float(PC_SERVICE_PRODUCT_MARGIN), 2)

            


            logger.info(f"Preparando producto para Shopify. ID: {pc_service_product_id} |- Precio: {cost_per_item} |- Precio con margen: {price_with_margin}")

            # Obtener los tags originales
            original_tag = product_data.get("tags")

            # Obtener el vendor (marca) del producto
            vendor_tag = product_data.get("extraData", {}).get("brand")

            # Dividir correctamente por el símbolo ">", limpiar comillas y reemplazar comas internas
            split_tags = [tag.strip().replace('"', '').replace(',', '.') for tag in original_tag.split(">")]

            # Asegurar que solo se manejen dos partes (Categoría y Subcategoría)
            if len(split_tags) == 2:
                # Ordenar: primero subcategoría, luego categoría
                reordered_tags = [split_tags[0], split_tags[1]]
            else:
                # Si no tiene ">", usar el tag tal cual
                reordered_tags = split_tags

            # Agregar el vendor como tag si existe
            if vendor_tag:
                reordered_tags.append(vendor_tag.strip())

            # Unir los tags correctamente (Shopify usa comas como separador)
            formatted_tags = ", ".join(reordered_tags)

            # Log de los tags formateados
            logger.info(f"Tags formateados: {formatted_tags}")

            #####################################################
            # Crear el payload para Shopify
            shopify_payload = {
                "product": {
                    "status": "draft",
                    "title": product_data.get("title"),
                    "body_html": product_data.get("body"),
                    "vendor": product_data.get("extraData", {}).get("brand"),
                    "product_type": product_data.get("type"),
                    "tags": formatted_tags,
                    "variants": [
                        {
                            "price": price_with_margin,
                            "cost": cost_per_item,
                            "sku": product_data.get("price", {}).get("sku"),
                            "inventory_management": "shopify",  # Shopify gestiona el stock
                            "inventory_quantity": product_data.get("availability", {}).get("stock", 0),
                            "barcode": product_data.get("extraData", {}).get("barcode")
                        }
                    ],
                    "images": [
                        {"src": variation.get("url")}
                        for image in product_data.get("images", [])
                        for variation in image.get("variations", [])
                    ]
                }
            }

            ##################################################################
            headers = {
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
            }

            #log payload
            logger.info(f"Payload para Shopify ######: {shopify_payload}")

            try:
                response = requests.post(SHOPIFY_API_URL, json=shopify_payload, headers=headers)

                if response.status_code == 201:
                    shopify_response = response.json()
                    shopify_product_id = shopify_response.get("product", {}).get("id", "ID no disponible")
                    logger.info(f"Producto con ID {pc_service_product_id} creado exitosamente en Shopify con ID de Shopify: {shopify_product_id}.")
                    results.append({
                        "pc_service_product_id": pc_service_product_id,
                        "status": "success",
                        "shopify_product_id": shopify_product_id,
                        "response": shopify_response
                    })

                    # Asignar el ID de PC Service como Metafield en Shopify
                    asignar_pc_service_id_y_proveedor(shopify_product_id, pc_service_product_id, "PC Service")
                else:
                    logger.error(f"Error al crear el producto en Shopify. ID {pc_service_product_id}, Respuesta: {response.text}")
                    results.append({"product_id": pc_service_product_id, "status": "error", "errors": response.json().get("errors", "Error desconocido")})
            except Exception as e:
                logger.error(f"Error procesando producto con ID {pc_service_product_id}: {e}")
                results.append({"pc_service_product_id": pc_service_product_id, "status": "error", "message": str(e)})

        return jsonify({"results": results}), 200

    except Exception as e:
        logger.error(f"Error en /api/shopify/create_products: {e}")
        return handle_error(str(e))
    
############################################################################################################
def asignar_pc_service_id_y_proveedor(product_id, pc_service_id, proveedor):
    """
    Asigna los Metafields 'pc_service_id' y 'proveedor' a un producto en Shopify.

    :param product_id: ID del producto en Shopify.
    :param pc_service_id: Valor del Metafield 'pc_service_id'.
    :param proveedor: Nombre del proveedor (nuevo Metafield).
    """
    #log params
    logger.info(f"product_id: {product_id}, pc_service_id: {pc_service_id}, proveedor: {proveedor}")
    SHOPIFY_API_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}"
    url = f"{SHOPIFY_API_URL}/products/{product_id}/metafields.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
    }

    # Definir los Metafields a crear
    metafields = [
        {
            "namespace": "custom",  # Namespace organizacional
            "key": "pc_service_id",  # Clave del primer Metafield
            "value": int(pc_service_id),
            "type": "number_integer"
        },
        {
            "namespace": "custom",  # Namespace organizacional
            "key": "proveedor",  # Clave del nuevo Metafield
            "value": proveedor,
            "type": "single_line_text_field"
        }
    ]

    for metafield in metafields:
        payload = {"metafield": metafield}

        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                logging.info(f"✅ Metafield '{metafield['key']}' asignado correctamente al producto {product_id}.")
            else:
                logging.error(f"❌ Error al asignar el Metafield '{metafield['key']}' al producto {product_id}: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"❌ Error inesperado al asignar el Metafield '{metafield['key']}' al producto {product_id}: {e}")


############################################################################################################
def get_product_details_internal(data):
    try:
        # Validar el formato de entrada
        if not isinstance(data, list):
            return {"error": "El parámetro debe ser una lista de objetos que contengan 'productID' y 'category_path'."}, 400

        # Limitar la cantidad de productos a procesar
        MAX_PRODUCTS = 10
        if len(data) > MAX_PRODUCTS:
            return {"error": f"El límite máximo de productos a consultar es {MAX_PRODUCTS}."}, 400

        token = get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}

        results = []

        for item in data:
            try:
                product_id = str(item.get("productID"))
                category_path = item.get("category_path")

                #log product_id and category_path
                logger.debug(f"product_id: {product_id}, category_path: {category_path}")

                # Validar que los campos necesarios estén presentes y sean válidos
                if not product_id or not isinstance(product_id, str) or not product_id.isdigit():
                    results.append({
                        "product_id": product_id,
                        "status": "error",
                        "message": "El ID del producto debe ser un número válido."
                    })
                    continue

                if not category_path or not isinstance(category_path, str) or not category_path.strip():
                    results.append({
                        "product_id": product_id,
                        "status": "error",
                        "message": "La categoría del producto debe ser una cadena no vacía."
                    })
                    continue

                product_id = int(product_id)
                if product_id <= 0:
                    results.append({
                        "product_id": product_id,
                        "status": "error",
                        "message": "El ID del producto debe ser un número positivo."
                    })
                    continue

                url = f"{BASE_URL}/products/{product_id}"
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    product_data = response.json()

                    # Agregar la categoría como 'tags'
                    product_data['tags'] = category_path

                    results.append({
                        "product_id": product_id,
                        "status": "success",
                        "data": product_data
                    })
                else:
                    error_message = response.json().get("message", "Error desconocido")
                    results.append({
                        "product_id": product_id,
                        "status": "error",
                        "message": error_message
                    })

            except ValueError:
                results.append({
                    "product_id": product_id,
                    "status": "error",
                    "message": "El ID del producto debe ser un número válido."
                })
            except Exception as e:
                logger.error(f"Error al consultar producto con ID {product_id}: {e}")
                results.append({
                    "product_id": product_id,
                    "status": "error",
                    "message": str(e)
                })

        return {"results": results}, 200

    except Exception as e:
        logger.error("Error en get_product_details_internal: %s", str(e))
        return {"error": str(e)}, 500




############################################################################################################
# Directorio donde se encuentran los archivos CSV
# Definir la ruta al directorio de los CSV (relativa al script)
BASE_DIR = Path(__file__).resolve().parent
CSV_DIRECTORY = BASE_DIR.parent / "updates_products_csv"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@app.route('/api/data', methods=['GET'])
def serve_csv_as_json():
    # Obtener la fecha actual o usar el parámetro `date`
    file_date = request.args.get('date', pd.Timestamp.now().strftime('%d_%m_%Y'))
    file_name = f"{file_date}.csv"
    
    # Construir la ruta del archivo CSV
    file_path = CSV_DIRECTORY / file_name
    #log file_path
    logger.info(f"file_path: {file_path}")

    

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

############################################################################################################
def handle_error(message, status_code=500):
    return jsonify({"error": message}), status_code

if __name__ == '__main__':
    try:
        api_token = authenticateOnPCService()
        logger.info("Servidor api_server iniciado y autenticado.")
        app.run(host='0.0.0.0', port=5001, debug=True)
    except Exception as e:
        logger.error("Error al iniciar el servidor: %s", str(e))
