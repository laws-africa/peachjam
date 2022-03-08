from django.test import TestCase

class HomeViewTest(TestCase):
  @classmethod
  def setUpTestData(cls):
    pass

  def test_home_page(self):
    response = self.client.get('/')
    self.assertTemplateUsed(response, 'peach_jam/home.html')
