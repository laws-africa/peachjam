web: gunicorn -c gunicorn.conf.py --worker-class peachjam.asgi.DjangoUvicornWorker --max-requests 10000 --max-requests-jitter 1000 peachjam.asgi:application -t 600 --log-file -
tasks: python manage.py process_tasks
