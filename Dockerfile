FROM python:3.8-bullseye
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# LibreOffice
RUN apt-get update && apt-get install -y libreoffice poppler-utils

# Production-only dependencies
RUN pip install psycopg2==2.9.3 gevent==21.12.0 gunicorn==20.1.0

# node
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get install -y nodejs

# Copy the code
COPY . /app
WORKDIR /app

# install dependencies
RUN pip install .

# install sass for compiling assets before deploying
RUN npm i -g sass

# install runtime node dependencies
RUN npm ci --no-audit --ignore-scripts --only=prod
