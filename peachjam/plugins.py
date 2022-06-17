from collections import defaultdict


class PluginRegistry:
    registry = defaultdict(dict)

    def register(self, topic, name=None):
        """Class decorator that registers a new class with the registry."""

        def wrapper(cls):
            self.registry[topic][name or cls.__name__] = cls
            return cls

        return wrapper


plugins = PluginRegistry()
