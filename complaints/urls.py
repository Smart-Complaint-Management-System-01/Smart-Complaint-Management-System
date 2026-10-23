from django.urls import path

from config.views import coming_soon
from . import views

app_name = "complaints"

urlpatterns = [
    # FR-05 - Prajna
    path("complaints/", coming_soon, name="my_list"),
    # FR-04 - Prajna
    path("complaints/new/", views.new_complaint, name="new"),
    path(
        "complaints/<str:complaint_id>/submitted/",
        views.submission_confirmation,
        name="submission_confirmation",
    ),
    # FR-08 - Rakshita
    path("admin/complaints/", coming_soon, name="admin_list"),
]
