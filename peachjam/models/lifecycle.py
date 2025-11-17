from typing import List

from django_lifecycle import AFTER_SAVE, LifecycleModelMixin, hook


class AttributeHooksMixin(LifecycleModelMixin):
    """Makes LifecycleChangesMixin work only when track_changes() is called. This means that we don't duplicate
    state in memory when it's not necessary (99% of the time).

    When we know an object will be changed and want to respond to attribute changes, call obj.track_changes()
    """

    def __init__(self, *args, **kwargs):
        # explicitly skip the __init__ from LifecycleModelMixin
        super(LifecycleModelMixin, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if "skip_hooks" not in kwargs:
            # don't use the functionality if it's not setup
            if not hasattr(self, "_initial_state"):
                kwargs["skip_hooks"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # skip functionality if not set up
        if hasattr(self, "_initial_state"):
            return super().delete(*args, **kwargs)
        else:
            return super(LifecycleModelMixin, self).delete(*args, **kwargs)

    def refresh_from_db(self, *args, **kwargs):
        # explicitly skip the __init__ from LifecycleModelMixin
        super(LifecycleModelMixin, self).refresh_from_db(*args, **kwargs)
        if hasattr(self, "_initial_state"):
            self._reset_initial_state()

    def track_changes(self):
        """Enables state tracking which is required for hooks to work."""
        self._reset_initial_state()


def lifecycle_hook(target_cls, *hook_args, **hook_kwargs):
    """Decorator to install django-lifecycle attribute hooks from outside the class.

    The obj.track_changes() must be called on the object before this will be triggered.

    Example usage:

        @lifecycle_hook(Judgment, AFTER_SAVE, when="case_summary", has_changed=True)
        def when_case_summary_changed(obj):
            ...
    """

    def decorator(func):
        wrapped = hook(*hook_args, **hook_kwargs)(func)
        setattr(target_cls, f"_attr_hook_{func.__name__}", wrapped)
        return wrapped

    return decorator


def after_attribute_changed(target_cls, when: str | List[str]):
    """Decorator to install an AFTER_SAVE django-lifecycle hook when one on more attributes change on a class.

    The obj.track_changes() must be called on the object before this will be triggered.

    Example usage:

        @after_attribute_changed(Judgment, "case_summary"):
        def when_case_summary_changed(obj):
            ...
    """
    return lifecycle_hook(target_cls, AFTER_SAVE, when=when, has_changed=True)
