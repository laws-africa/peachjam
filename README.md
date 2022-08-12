# Peach Jam

![Liiweb icon](https://laws.africa/img/icons/liiweb.png)


Project Peach Jam


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
pip install -r requirements.txt
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
cd peachjam && django-admin makemessages -a
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
