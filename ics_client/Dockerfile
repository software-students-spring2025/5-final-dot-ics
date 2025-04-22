FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    make \
    gcc \
    git \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pipenv

WORKDIR /app

COPY Pipfile .
COPY Pipfile.lock .

RUN pipenv install --deploy --system

COPY . .

CMD ["python", "client.py"]
