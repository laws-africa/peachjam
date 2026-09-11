from django.test import TestCase
from django.urls import reverse


class HomePageViewTest(TestCase):
    def test_search_form_is_a_key_link(self):
        response = self.client.get(reverse("home_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-key-link-feature="search"')
        self.assertContains(response, 'data-key-link="search"')
        self.assertContains(response, 'data-key-link="advanced_search"')
