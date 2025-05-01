import datetime
import heapq
from itertools import groupby

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, TemplateView

from peachjam.models import UserFollowing


class UserFollowingForm(forms.ModelForm):
    class Meta:
        model = UserFollowing
        fields = (
            "court",
            "author",
            "court_class",
            "court_registry",
            "country",
            "locality",
            "taxonomy",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields:
            self.fields[field].widget = forms.HiddenInput()


class UserFollowingButtonView(TemplateView):
    template_name = "peachjam/user_following_button.html"

    def get(self, *args, **kwargs):
        form = UserFollowingForm(self.request.GET)
        if form.is_valid():
            if self.request.user.is_authenticated:
                follow = UserFollowing.objects.filter(
                    **form.cleaned_data, user=self.request.user
                ).first()
                if follow:
                    return HttpResponseRedirect(
                        reverse("user_following_delete", kwargs={"pk": follow.pk})
                        + f"?{self.request.GET.urlencode()}"
                    )
                return HttpResponseRedirect(
                    reverse("user_following_create")
                    + f"?{self.request.GET.urlencode()}"
                )
            return super().get(*args, **kwargs)
        # invalid form, return empty response i.e no button
        return HttpResponse(status=400)


class BaseUserFollowingView(LoginRequiredMixin, PermissionRequiredMixin):
    model = UserFollowing

    def get_queryset(self):
        return self.request.user.following.all()


class UserFollowingListView(BaseUserFollowingView, ListView):
    permission_required = "peachjam.view_userfollowing"
    tab = "user_following"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # optional before_date parameter
            before_date = datetime.date.fromisoformat(self.request.GET.get("before"))
        except (TypeError, ValueError):
            before_date = None

        context["following_timeline"] = timeline = get_user_following_timeline(
            self.request.user,
            10,
            50,
            before_date,
        )
        if timeline:
            context["before_date"] = list(timeline.keys())[-1]
        return context

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/my/_following_timeline.html"]
        return ["peachjam/user_following_list.html"]


class UserFollowingCreateView(BaseUserFollowingView, CreateView):
    form_class = UserFollowingForm
    template_name = "peachjam/user_following_create.html"
    permission_required = "peachjam.add_userfollowing"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = UserFollowing()
        instance.user = self.request.user
        kwargs["instance"] = instance
        kwargs["data"] = self.request.GET or self.request.POST
        return kwargs

    def get_success_url(self):
        return (
            reverse("user_following_delete", kwargs={"pk": self.object.pk})
            + f"?{self.request.GET.urlencode()}"
        )


class UserFollowingDeleteView(BaseUserFollowingView, DeleteView):
    template_name = "peachjam/user_following_delete.html"
    permission_required = "peachjam.delete_userfollowing"

    def get_success_url(self):
        return reverse("user_following_button") + f"?{self.request.GET.urlencode()}"


def get_user_following_timeline(user, docs_per_source, max_docs, before_date=None):
    # Get the latest documents from all followed sources
    def apply_filter(qs):
        if before_date:
            qs = qs.filter(created_at__lt=before_date)
        return qs

    sources = [
        (
            f,
            apply_filter(
                f.get_documents_queryset()
                .order_by("-created_at")
                .select_related("work")
                .prefetch_related("labels", "taxonomies")
            ).iterator(max_docs),
        )
        for f in user.following.all()
    ]
    sources = merge_sources_by_date(sources, "created_at")

    # group the (source, document) tuples by date
    n_docs = 0
    groups_by_date = {}
    for day, doc_group in groupby(sources, lambda p: p[1].created_at.date()):
        doc_group = list(doc_group)
        n_docs += len(doc_group)

        # group the days documents by source, and put the smallest groups first
        groups = {}
        for source, doc in doc_group:
            groups.setdefault(source, []).append(doc)

        # cap documents per source
        for source, docs in groups.items():
            docs = sorted(docs, key=lambda d: d.date, reverse=True)
            groups[source] = (docs[:docs_per_source], docs[docs_per_source:])

        # tuples: (source, (docs, rest))
        groups_by_date[day] = sorted(
            groups.items(), key=lambda x: len(x[1][0]) + len(x[1][1])
        )

        if max_docs and n_docs > max_docs:
            break

    return groups_by_date


def merge_sources_by_date(sources, date_attr):
    """Merge multiple following sources into a single iterator of documents, ordered by date.
    sources: (source, Iterator[Document])
    Yields (source, document) in descending date order across all sources.
    """
    heap = []
    source_iters = {}

    # Prime heap
    for source, docs in sources:
        source_iters[source] = docs
        try:
            doc = next(docs)
            heapq.heappush(heap, (-getattr(doc, date_attr).toordinal(), source, doc))
        except StopIteration:
            continue

    while heap:
        _, source, doc = heapq.heappop(heap)
        yield source, doc

        # Refill from this source
        try:
            next_doc = next(source_iters[source])
            heapq.heappush(
                heap, (-getattr(next_doc, date_attr).toordinal(), source, next_doc)
            )
        except StopIteration:
            continue
