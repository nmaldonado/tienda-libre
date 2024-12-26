from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import os
import logging
import sys
sys.stderr = sys.stdout

app = Flask(__name__)
CORS(app)  # Permitir solicitudes desde cualquier origen (frontend)

# Directorio donde se encuentran los archivos CSV
CSV_DIRECTORY = "updates_productos_csv"
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


if __name__ == '__main__':
    try:

        logger.info("Servidor 1 iniciado y autenticado.")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error("Error al iniciar el servidor: %s", str(e))

