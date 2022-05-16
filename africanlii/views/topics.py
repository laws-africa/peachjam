from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import DocumentTopic, Taxonomy


class TopicsView(TemplateView):
    template_name = "africanlii/topics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topics_list = Taxonomy.objects.all()
        slug = kwargs.get("slug")
        topic = get_object_or_404(Taxonomy, slug=slug)
        topics_qs = Taxonomy.get_tree(parent=topic)
        document_list = DocumentTopic.objects.filter(topic__in=topics_qs)

        paginator = Paginator(document_list, 20)
        page = self.request.GET.get("page")
        try:
            documents = paginator.page(page)
        except PageNotAnInteger:
            documents = paginator.page(1)
        except EmptyPage:
            documents = paginator.page(paginator.num_pages)

        context["page_obj"] = documents
        context["topic"] = topic
        context["topic_list"] = topics_list

        return context
