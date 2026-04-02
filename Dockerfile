ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip curl bash

WORKDIR /app

# Copia tutto il repo (includendo index.html, app.js, style.css)
COPY . /app/

# Crea una cartella static IN PYTHON, NON nel Dockerfile
# (vedi server.py sotto)

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]