from typing import Any

from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from django.shortcuts import render
from django.views.generic import ListView

from peachjam.models import Collection

User = get_user_model()


class CollectionListView(ListView):
    model = Collection
    template_name = "peachjam/collections_list.html"
    context_object_name = "collections"
    navbar_link = "collections"
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Any]:
        # print(super().get_queryset().filter(user=User(self.request.user.id)))
        return super().get_queryset().filter(user=User(self.request.user.id))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        return context

    def render_collections(self, request):
        return render(request, "peachjam/collections_list.html")
