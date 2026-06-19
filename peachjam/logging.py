import logging
from contextlib import contextmanager

try:
    from asgiref.local import Local
except ImportError:
    from threading import local as Local


local = Local()
missing = object()


@contextmanager
def log_context(task_run_id=None):
    kwargs = {"task_run_id": task_run_id}
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
        task_run_id = getattr(record, "task_run_id", None) or getattr(
            local, "task_run_id", None
        )
        record.task_run_id = task_run_id or "none"
        record.correlation_id = (
            task_run_id or getattr(record, "request_id", None) or "none"
        )
        return True
