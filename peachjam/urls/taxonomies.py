from django.urls import path
from django.views.generic import RedirectView

from peachjam.views import TaxonomyDetailView, TaxonomyFirstLevelView, TaxonomyListView

urlpatterns = [
    path("", TaxonomyListView.as_view(), name="top_level_taxonomy_list"),
    path(
        "collections",
        RedirectView.as_view(pattern_name="top_level_taxonomy_list", permanent=True),
        name="taxonomy_collections",
    ),
    path(
        "<slug:topic>",
        TaxonomyFirstLevelView.as_view(),
        name="first_level_taxonomy_list",
    ),
    path(
        "<slug:topic>/<slug:child>",
        TaxonomyDetailView.as_view(),
        name="taxonomy_detail",
    ),
]
