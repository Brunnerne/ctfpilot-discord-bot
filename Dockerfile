FROM python:alpine

WORKDIR /app

COPY src/requirements.txt /app/requirements.txt

RUN apk add --no-cache gcc musl-dev libffi-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del gcc musl-dev libffi-dev

COPY src/ /app/

CMD ["python", "main.py"]