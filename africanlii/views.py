from django.views.generic import ListView, DetailView

from africanlii.models import Judgment


class JudgmentListView(ListView):
    template_name = 'africanlii/judgment_list.html'
    context_object_name = 'judgments'

    def get_queryset(self):
        return Judgment.objects.all()


class JudgmentDetailView(DetailView):
    model = Judgment
    template_name = 'africanlii/judgment_detail.html'
    context_object_name = 'judgment'
