from django.views import generic
from peach_jam.models import Decision

class DecisonListView(generic.ListView):
    template_name = 'peach_jam/decision_list.html'
    context_object_name = 'decisions'

    def get_queryset(self):
        return Decision.objects.all()

class DecisionOverviewView(generic.DetailView):
    model = Decision
    template_name = 'peach_jam/decision_overview.html'
    context_object_name = 'decision'

