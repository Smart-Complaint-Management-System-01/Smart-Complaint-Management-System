
from django.urls import path

from config.views import coming_soon
from . import views

app_name = "complaints"

urlpatterns = [
    # FR-05 - Prajna
    path("complaints/", views.my_complaints, name="my_list"),
    # FR-04 - Prajna
    path("complaints/new/", coming_soon, name="new"),
    # FR-08 - Rakshita
    path("admin/complaints/", coming_soon, name="admin_list"),
]
