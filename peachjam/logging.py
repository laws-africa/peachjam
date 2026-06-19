import logging
from contextlib import contextmanager

try:
    from asgiref.local import Local
except ImportError:
    from threading import local as Local


local = Local()
missing = object()
empty = "-"


@contextmanager
def log_context(task_run_id=missing, frbr_uri=missing):
    kwargs = {
        key: value
        for key, value in {
            "task_run_id": task_run_id,
            "frbr_uri": frbr_uri,
        }.items()
        if value is not missing and value is not None
    }
    old_values = {key: getattr(local, key, missing) for key in kwargs}
    try:
        for key, value in kwargs.items():
            setattr(local, key, value)
        yield
    finally:
        for key, value in old_values.items():
            if value is missing:
                try:
                    delattr(local, key)
                except AttributeError:
                    pass
            else:
                setattr(local, key, value)


class LoggingContextFilter(logging.Filter):
    def filter(self, record):
        task_run_id = getattr(local, "task_run_id", None)
        record.task_run_id = task_run_id or empty
        record.correlation_id = (
            task_run_id or getattr(record, "request_id", None) or empty
        )
        record.frbr_uri = getattr(local, "frbr_uri", None) or empty
        return True
