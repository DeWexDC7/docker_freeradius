FROM python:3.9-slim

# Instalar dependencias necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    systemctl && \
    rm -rf /var/lib/apt/lists/*

# Instalar psycopg2
RUN pip install psycopg2-binary

# Copiar el script y los archivos de configuración
WORKDIR /app
COPY failover_monitor.py /app/
COPY config /config

# Comando para ejecutar el script
CMD ["python", "failover_monitor.py"]
