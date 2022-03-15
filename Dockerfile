FROM python:3.7-bullseye
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY requirements.txt /tmp/requirements.txt
RUN pip install -q --upgrade pip \
  && pip install -q --upgrade setuptools \
  && pip install -q -r /tmp/requirements.txt

# node
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash -
RUN apt-get install -y nodejs

# Copy the code
COPY . /app
WORKDIR /app

# install npm requirements
RUN npm ci --no-audit --prefer-offline
RUN npx webpack -p
