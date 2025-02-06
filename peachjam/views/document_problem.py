from django.http import HttpResponse
from django.views.generic.edit import View

from peachjam.forms import DocumentProblemForm


class DocumentProblemView(View):
    form_class = DocumentProblemForm
    http_method_names = ["post"]

    def post(self, *args, **kwargs):
        # fire-and-forget
        form = self.form_class(self.request.POST)
        if form.is_valid():
            form.send_email()
            return HttpResponse()
        return HttpResponse(status=400)
