from modeltranslation.translator import TranslationOptions, register

from peachjam_subs.models import Feature, Product


@register(Feature)
class FeatureTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
    )
