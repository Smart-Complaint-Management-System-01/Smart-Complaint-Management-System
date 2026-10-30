from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ComplaintFormUsabilityTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="u@x.com", email="u@x.com", password=None)
        self.client.force_login(user)  # a normal USER; admins cannot lodge complaints
        self.response = self.client.get(reverse("complaints:new"))
        self.html = self.response.content.decode()

    def test_page_loads(self):
        self.assertEqual(self.response.status_code, 200)

    def test_required_fields_are_marked(self):
        # one * per required field (category, title, description) plus the legend
        self.assertGreaterEqual(self.html.count('class="required"'), 3)
        self.assertContains(self.response, "are required")

    def test_double_submit_protection_enabled(self):
        self.assertContains(self.response, "data-once")

    def test_submit_button_has_plain_label(self):
        self.assertContains(self.response, "Submit complaint")

    def test_main_js_is_linked(self):
        self.assertContains(self.response, "js/main.js")