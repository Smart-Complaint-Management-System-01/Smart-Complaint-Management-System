from django.contrib.auth import get_user_model
from django.test import TestCase

from complaints.models import Complaint

User = get_user_model()


class PersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u@x.com", email="u@x.com", password=None)

    def make(self, **kw):
        data = dict(user=self.user, category="OTHER", title="A title", description="A long enough description text.")
        data.update(kw)
        return Complaint.objects.create(**data)

    def test_saved_complaint_can_be_retrieved_fresh_from_db(self):
        saved = self.make()
        fetched = Complaint.objects.get(complaint_id=saved.complaint_id)
        self.assertEqual(fetched.title, "A title")
        self.assertEqual(fetched.user, self.user)

    def test_complaint_id_format_and_uniqueness(self):
        ids = {self.make().complaint_id for _ in range(5)}
        self.assertEqual(len(ids), 5)
        self.assertTrue(all(i.startswith("CMP-") for i in ids))

    def test_id_not_regenerated_on_update(self):
        c = self.make()
        original = c.complaint_id
        c.title = "Edited"
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.complaint_id, original)

    def test_default_status_is_submitted(self):
        self.assertEqual(self.make().status, Complaint.Status.SUBMITTED)

    def test_complaints_deleted_with_user_not_orphaned(self):
        self.make()
        self.user.delete()
        self.assertEqual(Complaint.objects.count(), 0)