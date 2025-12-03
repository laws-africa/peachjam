# Peach Jam

![Liiweb icon](https://laws.africa/img/icons/liiweb.png)


Project Peach Jam

## Prerequisites
- Python@3.10
- postgresql > 14
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
pip install -e .[dev]
pip install psycopg[binary]==3.2.12
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

- Install the required frontend dependencies (Node modules) located in the `peachjam` directory:
```
npm install
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
python manage.py loaddata ./peachjam/fixtures/documents/sample_documents.json
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

Translations for strings are added on [CrowdIn](https://laws-africa.crowdin.com/).

Django translations are stored in the `locale` directories under each sub-project. Javascript and Vue translations are stored in `peachjam/js/locale/en/translation.json`.

If you have added or changed strings that need translating, you must [tell Django to update the .po files](https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#localization-how-to-create-language-files) so that translations can be supplied through CrowdIn.

```bash
scripts/extract-translations.sh
```

And then commit the changes. CrowdIn will pick up any changed strings and make them available for translation. Once they are translated, it will open a pull request to merge the changes into `main`.

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


## Deployment
Please refer to the [deployment documentation](DEPLOYMENT.md).

# License

Copyright 2023 Laws.Africa.

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
