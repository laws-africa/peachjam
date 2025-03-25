FROM python:3.10-bullseye
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# LibreOffice
RUN apt-get update && apt-get install -y libreoffice poppler-utils pandoc

# Production-only dependencies
RUN pip install psycopg2==2.9.3 gunicorn==21.2.0

# node
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash -
RUN apt-get install -y nodejs

# install sass for compiling assets before deploying
RUN npm i -g sass

# install puppeteer and chrome for generating images
RUN npm i -g puppeteer
RUN npx puppeteer browsers install chrome

# install dependencies
# copying this in first means Docker can cache this operation
COPY pyproject.toml /app/
# this dir is needed by pip when processing pyproject.toml
COPY bin /app/bin
WORKDIR /app
RUN pip install .

# install runtime node dependencies
# copying this in first means Docker can cache this operation
COPY package*.json /app/
RUN npm ci --no-audit --ignore-scripts --only=prod

ENV NODE_PATH=/app/node_modules/

# Copy the code
COPY . /app
