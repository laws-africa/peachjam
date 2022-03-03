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

- Ensure you have PostgreSQL installed and running. Create a postgresql user with username and password peach_jam, and create a corresponding database called peach_jam.

```
sudo su - postgres -c 'createuser -d -P peach_jam'
sudo su - postgres -c 'createdb peach_jam'
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

