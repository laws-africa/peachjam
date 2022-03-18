from django.test import TestCase


class HomeViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def test_login_page(self):
        response = self.client.get('/accounts/login/')
        self.assertTemplateUsed(response, 'account/login.html')
