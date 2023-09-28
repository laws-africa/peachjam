from django.http import HttpResponse
from django.views.generic.edit import FormView

from peachjam.forms import DocumentProblemForm


class DocumentProblemView(FormView):
    template_name = "peachjam/_report_issue_modal.html"
    form_class = DocumentProblemForm

    def form_valid(self, form):
        # fire-and-forget
        form.send_email()
        return HttpResponse()
