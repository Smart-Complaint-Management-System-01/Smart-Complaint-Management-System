from django.urls import path

from complaints.views import admin_detail, admin_list, my_list, new_complaint

app_name = "complaints"

urlpatterns = [
    # FR-05 - Prajna
    path("complaints/", my_list, name="my_list"),
    # FR-04 - Prajna
    path("complaints/new/", new_complaint, name="new"),
    # FR-08 - Rakshita
    path("admin/complaints/", admin_list, name="admin_list"),
    path("admin/complaints/<int:pk>/", admin_detail, name="admin_detail"),
]
