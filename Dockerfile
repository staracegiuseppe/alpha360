ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip curl bash

WORKDIR /app

RUN mkdir -p /app/webapp

COPY index.html /app/webapp/index.html

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . /app/

RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]