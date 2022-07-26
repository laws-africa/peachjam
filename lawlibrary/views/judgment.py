from django.views.generic import ListView

from peachjam.models import Judgment


class JudgmentListView(ListView):
    model = Judgment
    template_name = "lawlibrary/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20
