from django.core.checks import Error, Tags, register

from peachjam.models.lifecycle import AttributeCycleError, attribute_dag


@register(Tags.models)
def check_attribute_dag_is_acyclic(app_configs, **kwargs):
    try:
        attribute_dag.assert_acyclic()
    except AttributeCycleError as exc:
        return [
            Error(
                str(exc),
                id="peachjam.E001",
            )
        ]
    return []
