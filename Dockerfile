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

# install runtime node dependencies
# copying this in first means Docker can cache this operation
COPY package*.json /app/
WORKDIR /app
RUN npm ci --no-audit --ignore-scripts --omit=dev

# install chrome for generating images
RUN npx puppeteer browsers install chrome

# install python dependencies
# copying this in first means Docker can cache this operation
COPY pyproject.toml /app/
RUN pip install .

ENV NODE_PATH=/app/node_modules/

# Copy the code
COPY . /app
