from django.shortcuts import render
from django.views.generic.edit import FormView

from peachjam.forms import DocumentProblemForm


class DocumentProblemView(FormView):
    template_name = "peachjam/_report_issue_modal.html"
    form_class = DocumentProblemForm

    def form_valid(self, form):
        email_sent = form.send_email()
        if email_sent:
            return render(
                self.request, "peachjam/emails/document_issue_email_success.html"
            )
        else:
            return render(
                self.request, "peachjam/emails/document_issue_email_error.html"
            )
