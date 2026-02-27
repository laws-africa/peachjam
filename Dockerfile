FROM ubuntu:24.04

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# python 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev \
    ca-certificates build-essential

# LibreOffice, pdftotext, pandoc
RUN apt-get install -y libreoffice poppler-utils pandoc \
    && rm -rf /var/lib/apt/lists/*

# Production-only dependencies, or dependencies that take a long time to install.
RUN pip install psycopg==3.2.12 gunicorn==21.2.0 scikit-learn==1.6.1 numpy==2.1.3

# node
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash -
RUN apt-get install -y nodejs

# Create and activate venv
RUN python3.12 -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# upgrade pip and friends
RUN python -m pip install --upgrade pip setuptools wheel

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
# this dir is needed by pip when processing pyproject.toml
COPY bin /app/bin
RUN pip install '.[ml]'

ENV NODE_PATH=/app/node_modules/

# Copy the code
COPY . /app
