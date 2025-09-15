import os

# set gunicorn proc name
proc_name = os.getenv("APP_NAME", "peachjam")
