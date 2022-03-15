from django.views import generic
from peach_jam.models import Decision
from peach_jam.forms import DecisionFilterForm

class DecisonListView(generic.ListView):
    template_name = 'peach_jam/decision_list.html'
    context_object_name = 'decisions'

    def get_queryset(self):
        return Decision.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = DecisionFilterForm()
        return context

    # def get(self, request, *args, **kwargs):
    #     self.form = DecisionFilterForm(request.GET)
    #     self.form.is_valid()

    #     return super(DecisonListView, self).get(request, *args, **kwargs)
class DecisionDetailView(generic.DetailView):
    model = Decision
    template_name = 'peach_jam/decision_detail.html'
    context_object_name = 'decision'





