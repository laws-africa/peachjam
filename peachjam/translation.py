from modeltranslation.translator import TranslationOptions, register

from peachjam.models import (
    AttachedFileNature,
    Court,
    CourtClass,
    CourtRegistry,
    CustomPropertyLabel,
    DocumentNature,
    Label,
    Outcome,
    Predicate,
    Taxonomy,
    Treatment,
)


@register(AttachedFileNature)
class AttachedFileNatureTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Court)
class CourtTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(CourtClass)
class CourtClassTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(CourtRegistry)
class CourtRegistryTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(DocumentNature)
class DocumentNatureTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Label)
class LabelTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Outcome)
class OutcomeTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Predicate)
class PredicateTranslationOptions(TranslationOptions):
    fields = ("verb", "reverse_verb")


@register(Taxonomy)
class TaxonomyTranslationOptions(TranslationOptions):
    fields = ("name", "path_name")


@register(CustomPropertyLabel)
class CustomPropertyLabelTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Treatment)
class TreatmentTranslationOptions(TranslationOptions):
    fields = ("name",)
