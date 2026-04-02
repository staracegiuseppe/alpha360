ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-pip curl bash

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . /app/

# se nel repo hai 'webapp/dist/index.html'
COPY index.html /app/webapp


RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
