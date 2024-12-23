#!/bin/bash

# Directorio del entorno virtual
VENV_DIR="/venv"

# Directorio donde están los scripts Python
SCRIPT_DIR="."

# Activar el entorno virtual
source "$VENV_DIR/Scripts/activate"

# Función para iniciar un script Python
start_script() {
    local script_name=$1
    local log_file=$2

    echo "Iniciando $script_name..."
    nohup python "$script_name" > "$log_file" 2>&1 &
    echo "$script_name iniciado con PID $!"
}

# Iniciar cada script con logs separados
start_script "$SCRIPT_DIR/app.py" "$SCRIPT_DIR/script1.log"
start_script "$SCRIPT_DIR/api_server.py" "$SCRIPT_DIR/script2.log"

# Mostrar procesos en ejecución
echo "Scripts en ejecución:"
ps aux | grep python
