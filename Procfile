web: gunicorn -c gunicorn.conf.py --worker-class gthread --threads 8 --max-requests 10000 --max-requests-jitter 1000 peachjam.wsgi:application -t 600 --log-file -
tasks: python manage.py process_tasks
