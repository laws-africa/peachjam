# Peach Jam

![Liiweb icon](https://laws.africa/img/icons/liiweb.png)


Project Peach Jam

## Prerequisites
- postgresql
- pip
- elasticsearch
- global sass

## Local Setup
- Clone the repository
```
git clone https://github.com/laws-africa/peach-jam.git
```

- Set up and activate a virtual environment.  Python 3.6 or later is required.
```
python3 -m venv .venv

source .venv/bin/activate

```
- Install requirements.
```
pip install -e .
pip install psycopg2-binary==2.9.3
```

- Ensure you have PostgreSQL installed and running. Create a postgresql user with username and password peachjam, and create a corresponding database called peachjam.

```
sudo su - postgres -c 'createuser -d -P peachjam'
sudo su - postgres -c 'createdb peachjam'
```


- You also have the option of exporting a custom database connection string as an environment variable named `DATABASE_URL` which will take precedence over the default.

```
export DATABASE_URL=postgres://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE_NAME>
```
- Run migrations to create tables.
```
python manage.py migrate
```

- Run the following command to create fixtures for languages and countries.
```
python manage.py setup_countries_languages
```

- To load sample documents for development purposes there is a fixture file included. Run the command

```
python manage.py loaddata ./peachjam/fixtures/documents/sample_documents.json.gz
```

- Create a superuser for the admin.

```
python manage.py createsuperuser
```

- You can now run the server
```
python manage.py runserver
```

## Setup pre-commit
The project has linting enabled using pre-commit. It runs on the CI pipeline, so you need to enable locally as well. Run the following to allow Precommit to format and fix any linting errors on your code.
```
pre-commit install
```

## Adding translation strings

Translations for the project are stored in the `locale` directory. Translations for strings are added on [CrowdIn](https://crowdin.com/project/lawsafrica-indigo).

If you have added or changed strings that need translating, you must [tell Django to update the .po files](https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#localization-how-to-create-language-files) so that translations can be supplied through CrowdIn.

```bash
for d in peachjam africanlii; do pushd $d; django-admin makemessages -a; popd; done
```

And then commit the changes. CrowdIn will pick up any changed strings and make them available for translation. Once they are translated, it will open a pull request to merge the changes into master.

Once merged into `main`, you must [tell Django to compile the .po files to .mo files](https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#compiling-message-files):

```bash
django-admin compilemessages
```

And then commit the changes.

## i18n-vue translations
Translations for `vue` components are stored in `peachjam/js/locale`.
If the translation syntax is added/updated/deleted (`$t()`), run the following command to update the  `json` files in
`peachjam/js/locale`
```
i18next './peachjam/js/**/*.{js,vue}'
```
And then commit the changes.
CrowdIn will pick up any changed strings on `main` and make them available for translation. Once they are translated,
it will open a pull request to merge the changes into `main`.

## Deployment
Peachjam can be deployed to a server that has [Dokku](https://dokku.com/) installed. This allows for easy config based deployments using Docker containers.
The following steps outline the procedure to deploy a new Peachjam based application.

#### Application Setup and Configuration
- SSH into the server with dokku installed and create a new application using Dokku's `apps:create` command

      dokku apps:create <app_name>
- Setup the domain for the application

      dokku domains:set <app_name> <domain_name>
- Add the relevant environment variables using the dokku config:set command. The required configuration values can be found in the env.example file.

      dokku config:set CONFIG1=value CONFIG2=value
-
#### SSL
- Enable LetsEncrypt for SSL/TLS. Dokku allows easy setup of SSL using the letsencrypt plugin. On the server, install the letsencrypt dokku plugin:

      sudo dokku plugin:install https://github.com/dokku/dokku-letsencrypt.git
- Configure letsencrypt with your email address, so you get reminders about renewing certificates:

      dokku config:set --no-restart <app_name> DOKKU_LETSENCRYPT_EMAIL=your@email.tld

- Install the certificate. Before you install the certificate, your website's domain name must be setup and pointing at this server, so that you can prove that you own the domain.

      dokku letsencrypt <app_name>

- Letsencrypt certificates expire every three months. Let's setup a cron job to renew certificates automatically:

      dokku letsencrypt:cron-job --add

- You can also manually renew a certificate when it's close to expiry:

      dokku letsencrypt:auto-renew


#### Build and Deploy
- Dokku will build and deploy the application automatically on git push. First add the remote to the git

      git remote add dokku dokku@<your_server_domain>:<app_name>
- To trigger a build and deploy

      git push dokku <branch_name>:master

#### Background Tasks

- Peachjam runs various background tasks as separate processes. They can be specified within the Procfile.
- On the dokku server, scale up the processes to run these tasks:

      dokku ps:scale <app_name> tasks=1 tasks2=1

## Admin theme

Peachjam customises the Django admin view using [Django Jazzmin](https://django-jazzmin.readthedocs.io/). We build
a custom bundle of Bootstrap 4 specifically for the admin area from the [jazzmin-theme](jazzmin-theme) directory.

To make changes to it:

```bash
cd jazzmin-theme
npm i
# make your changes to peachjam-jazzmin.scss
# ...
npm run watch
```

Once you're done, run:

```bash
npm run build
```

and commit both your changes, and the updated [peachjam/static/stylesheets/peachjam-jazzmin.css](peachjam/static/stylesheets/peachjam-jazzmin.css).

# License

Copyright 2022 Laws.Africa.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
