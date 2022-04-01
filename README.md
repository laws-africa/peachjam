# Peach Jam

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

- Create a superuser for the admin.

```
python manage.py createsuperuser
```

- You can now run the server
```
python manage.py runserver
```

### Setup Precommit
- Setup the precommit hooks that run on every commit:
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

Once merged into master, you must [tell Django to compile the .po files to .mo files](https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#compiling-message-files):

```bash
django-admin compilemessages
```

And then commit the changes.
