web: gunicorn --worker-class gthread --workers 2 --threads 8 peachjam.wsgi:application -t 600 --log-file -
tasks: python manage.py process_tasks
