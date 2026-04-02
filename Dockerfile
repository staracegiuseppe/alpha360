ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip curl bash

WORKDIR /app

# 1. Copia il frontend nella giusta posizione
COPY webapp /app/webapp

# 2. requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 3. Copia tutto il resto del codice Python
COPY . /app/

RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]