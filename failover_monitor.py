import psycopg2
from psycopg2 import OperationalError
import subprocess
import time
import logging

# Configuración del logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("failover_monitor.log"),  # Guardar logs en un archivo
        logging.StreamHandler()                      # Mostrar logs en la consola
    ]
)

# Configuración de las bases de datos
DB_MAIN = {
    "host": "main_db",  # Nombre del servicio Docker
    "port": 5432,
    "user": "postgres",
    "password": "admin",
    "dbname": "main_db"
}

DB_SUPPORT = {
    "host": "support_db",  # Nombre del servicio Docker
    "port": 5432,
    "user": "postgres",
    "password": "admin",
    "dbname": "support_db"
}

# Ruta al archivo de configuración del servidor RADIUS
RADIUS_CONFIG_PATH = "/config/radius.conf"

# Comando para reiniciar el servidor RADIUS
RADIUS_RESTART_COMMAND = ["systemctl", "restart", "radiusd"]

# Verificar conexión a PostgreSQL
def check_db_connection(db_config):
    try:
        logging.debug(f"Comprobando conexión a la base de datos: {db_config['host']}:{db_config['port']}")
        conn = psycopg2.connect(**db_config)
        conn.close()
        logging.info(f"Conexión exitosa a la base de datos: {db_config['host']}")
        return True
    except OperationalError as e:
        logging.warning(f"No se pudo conectar a la base de datos: {db_config['host']} - Error: {e}")
        return False

# Actualizar configuración del servidor RADIUS
def update_radius_config(db_service_name):
    try:
        logging.debug(f"Intentando actualizar la configuración de RADIUS para apuntar a: {db_service_name}")
        with open(RADIUS_CONFIG_PATH, "r") as file:
            config_lines = file.readlines()

        new_config_lines = []
        for line in config_lines:
            if "db_ip" in line:
                new_config_lines.append(f"db_ip = {db_service_name}\n")
            elif "db_port" in line:
                new_config_lines.append(f"db_port = 5432\n")  # Puerto fijo para ambas bases
            else:
                new_config_lines.append(line)

        with open(RADIUS_CONFIG_PATH, "w") as file:
            file.writelines(new_config_lines)

        # Reiniciar el servicio del servidor RADIUS
        subprocess.run(RADIUS_RESTART_COMMAND, check=True)
        logging.info(f"Servidor RADIUS actualizado correctamente para apuntar a: {db_service_name}")
    except Exception as e:
        logging.error(f"Error al actualizar la configuración del servidor RADIUS: {e}")

# Script de monitoreo
def failover_monitor():
    current_main = DB_MAIN  # El servidor principal actual
    logging.info(f"Iniciando el monitoreo de failover. Principal actual: {current_main['host']}")

    while True:
        # Verificar estado de las bases de datos
        main_status = check_db_connection(DB_MAIN)
        support_status = check_db_connection(DB_SUPPORT)

        if main_status and current_main != DB_MAIN:
            logging.info(f"El servidor principal {DB_MAIN['host']} está activo de nuevo. Restaurando como principal.")
            update_radius_config(DB_MAIN["host"])
            current_main = DB_MAIN

        elif not main_status and support_status and current_main != DB_SUPPORT:
            logging.warning(f"El servidor principal {DB_MAIN['host']} está caído. Cambiando a servidor de soporte {DB_SUPPORT['host']} como principal.")
            update_radius_config(DB_SUPPORT["host"])
            current_main = DB_SUPPORT

        elif not main_status and not support_status:
            logging.critical(f"Ambos servidores están inactivos. Requiere verificación manual. Último principal: {current_main['host']}")

        logging.debug(f"Estado actual: Principal -> {current_main['host']} | Main -> {'Activo' if main_status else 'Inactivo'} | Soporte -> {'Activo' if support_status else 'Inactivo'}")

        time.sleep(10)  # Esperar antes de la próxima verificación

if __name__ == "__main__":
    failover_monitor()
