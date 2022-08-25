FROM python:3.8-bullseye
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY requirements.txt /tmp/requirements.txt

# LibreOffice
RUN apt-get update && apt-get install -y libreoffice poppler-utils

RUN pip install -q --upgrade pip \
  && pip install -q --upgrade setuptools \
  && pip install -q -r /tmp/requirements.txt

# node
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get install -y nodejs

# Copy the code
COPY . /app
WORKDIR /app

# install sass for compiling assets before deploying
RUN npm i -g sass
