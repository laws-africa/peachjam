from collections import defaultdict
from dataclasses import dataclass
from typing import List

from django_lifecycle import AFTER_SAVE, LifecycleModelMixin, hook


class AttributeHooksMixin(LifecycleModelMixin):
    """Makes LifecycleChangesMixin work only when track_changes() is called. This means that we don't duplicate
    state in memory when it's not necessary (99% of the time).

    When we know an object will be changed and want to respond to attribute changes, call obj.track_changes()
    """

    _tracking_changes = False

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
        """Enables state tracking which is required for hooks to work. Idempotent."""
        if not self._tracking_changes:
            self._reset_initial_state()
            self._tracking_changes = True


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


@dataclass(frozen=True)
class AttributeHookMetadata:
    owner_class: str
    function_name: str
    timing: str
    declaration_mode: str
    trigger_attributes: tuple[str, ...]
    target_attributes: tuple[str, ...]


class AttributeDAG:
    """A lightweight in-memory registry of attribute dependency edges."""

    def __init__(self):
        self._edges = defaultdict(list)

    def clear(self):
        self._edges.clear()

    def add_rule(
        self,
        owner_class,
        function_name: str,
        timing: str,
        declaration_mode: str,
        trigger_attributes: list[str],
        target_attributes: list[str],
    ):
        metadata = AttributeHookMetadata(
            owner_class=owner_class.__name__,
            function_name=function_name,
            timing=timing,
            declaration_mode=declaration_mode,
            trigger_attributes=tuple(trigger_attributes),
            target_attributes=tuple(target_attributes),
        )
        for source in trigger_attributes:
            for target in target_attributes:
                edge = (source, target)
                if metadata not in self._edges[edge]:
                    self._edges[edge].append(metadata)

    def edges(self):
        return {edge: list(metadata) for edge, metadata in self._edges.items()}

    def nodes(self):
        values = set()
        for source, target in self._edges:
            values.add(source)
            values.add(target)
        return values

    def as_dict(self):
        nodes = set()
        for source, target in self._edges:
            nodes.add(source)
            nodes.add(target)
        return {
            "nodes": sorted(nodes),
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "metadata": [vars(item) for item in metadata],
                }
                for (source, target), metadata in sorted(self._edges.items())
            ],
        }


attribute_dag = AttributeDAG()


def _normalise_attributes(attributes):
    if isinstance(attributes, str):
        return [attributes]
    return list(attributes)


def _qualify_attribute(owner_class, attribute_name: str, local_only=False):
    """Qualify an attribute name relative to the owner class.

    If ``local_only`` is true, the attribute is always treated as belonging to the owner class,
    and any dotted prefix is ignored.
    """
    if local_only:
        return f"{owner_class.__name__}.{attribute_name.rsplit('.', 1)[-1]}"
    if "." in attribute_name:
        return attribute_name
    return f"{owner_class.__name__}.{attribute_name}"


def _register_attribute_hook(
    owner_class,
    func,
    timing,
    trigger_attributes,
    target_attributes,
    declaration_mode,
):
    trigger_attributes = [
        _qualify_attribute(owner_class, attr, local_only=True)
        for attr in _normalise_attributes(trigger_attributes)
    ]
    target_attributes = [
        _qualify_attribute(owner_class, attr)
        for attr in _normalise_attributes(target_attributes)
    ]
    when_any = [attr.split(".", 1)[1] for attr in trigger_attributes]

    wrapped = hook(timing, when_any=when_any, has_changed=True)(func)
    attribute_dag.add_rule(
        owner_class=owner_class,
        function_name=func.__name__,
        timing=timing,
        declaration_mode=declaration_mode,
        trigger_attributes=trigger_attributes,
        target_attributes=target_attributes,
    )
    return wrapped


def on_attribute_changed(*args):
    """This decorator uses django-lifecycle to install hooks that trigger when specified attributes change on a model
    instance. It's a robust way to implement attribute-level change hooks for derived attributes without having to
    manually track state or worry about the right lifecycle phase.

    It also records the attribute dependencies in the attribute DAG for inspection and cycle checking.

    Off-class usage:

        @on_attribute_changed(
            DocumentContent,
            AFTER_SAVE,
            ["source_html"],
            ["CoreDocument.citations"],
        )
        def extract_citations(doc_content):
            ...

    On-class usage:

        class Judgment(AttributeHooksMixin, models.Model):
            @on_attribute_changed(AFTER_SAVE, ["foo", "bar"], ["baz"])
            def update_baz(self):
                ...

    Parameters for off-class usage:
    ``target_cls``:
        The model class on which the hook should be installed.
    ``timing``:
        A django-lifecycle hook phase, typically ``BEFORE_SAVE`` or ``AFTER_SAVE``.
    ``trigger_attributes``:
        A string or list of strings naming source attributes on the hooked class that trigger the hook when changed.
        These are always treated as local attributes on the hooked class.
    ``target_attributes``:
        A string or list of strings naming the attributes that this hook conceptually updates.
        These are not validated. Unqualified names are interpreted relative to the hooked class,
        while qualified names such as ``"CoreDocument.citations"`` are preserved as-is.

    Parameters for on-class usage:
    ``timing``:
        A django-lifecycle hook phase, typically ``BEFORE_SAVE`` or ``AFTER_SAVE``.
    ``trigger_attributes``:
        A string or list of strings naming source attributes on the hooked class that trigger the hook when changed.
    ``target_attributes``:
        A string or list of strings naming the attributes that this hook conceptually updates.

    Notes:
    - For models using ``AttributeHooksMixin``, callers must still call ``track_changes()``
      before saving if they want change-based hooks to fire.
    - Trigger attributes are used to configure the real lifecycle hook on the hooked class.
    - Target attributes are only used to enrich the attribute DAG.
    """
    if len(args) != 4 and len(args) != 3:
        raise TypeError(
            "on_attribute_changed expects either 3 or 4 positional arguments"
        )

    if isinstance(args[0], type):
        owner_class, timing, trigger_attributes, target_attributes = args

        def decorator(func):
            wrapped = _register_attribute_hook(
                owner_class=owner_class,
                func=func,
                timing=timing,
                trigger_attributes=trigger_attributes,
                target_attributes=target_attributes,
                declaration_mode="off-class",
            )
            setattr(owner_class, f"_attr_hook_{func.__name__}", wrapped)
            return wrapped

        return decorator

    timing, trigger_attributes, target_attributes = args

    def decorator(func):
        class Descriptor:
            """Descriptor used to defer on-class hook registration until class creation."""

            def __init__(self, wrapped_func):
                self.func = wrapped_func
                self.__name__ = getattr(wrapped_func, "__name__", None)
                self.__doc__ = getattr(wrapped_func, "__doc__", None)

            def __set_name__(self, owner, name):
                wrapped = _register_attribute_hook(
                    owner_class=owner,
                    func=self.func,
                    timing=timing,
                    trigger_attributes=trigger_attributes,
                    target_attributes=target_attributes,
                    declaration_mode="on-class",
                )
                setattr(owner, name, wrapped)

        return Descriptor(func)

    return decorator


def after_attribute_changed(target_cls, attr: str | List[str]):
    """Decorator to install an AFTER_SAVE django-lifecycle hook when one on more attributes change on a class.

    The obj.track_changes() must be called on the object before this will be triggered.

    Example usage:

        @after_attribute_changed(Judgment, "case_summary"):
        def when_case_summary_changed(obj):
            ...
    """
    if not isinstance(attr, list):
        attr = [attr]
    return lifecycle_hook(target_cls, AFTER_SAVE, when_any=attr, has_changed=True)
