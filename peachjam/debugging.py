import threading

import debug_toolbar.utils


class ThreadCollector:
    def __init__(self):
        self.data = threading.local()
        self.data.collection = []

    def collect(self, item):
        if hasattr(self.data, "collection"):
            self.data.collection.append(item)

    def get_collection(self):
        return getattr(self.data, "collection", [])

    def clear_collection(self):
        self.data.collection = []


# monkey patch django debug toolbar so that elastic_panel's broken import still works
# see https://github.com/Benoss/django-elasticsearch-debug-toolbar/pull/21
debug_toolbar.utils.ThreadCollector = ThreadCollector
