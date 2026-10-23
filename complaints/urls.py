from django.urls import path

from config.views import coming_soon

from . import views

app_name = "complaints"

urlpatterns = [
    # FR-05 - Prajna
    path("complaints/", coming_soon, name="my_list"),
    # FR-04 - Prajna
    path("complaints/new/", coming_soon, name="new"),
    # FR-08 - Rakshita
        # FR-08 - Rakshita
    path("admin/complaints/", views.admin_list, name="admin_list"),
    path("admin/complaints/<int:pk>/", views.admin_detail, name="admin_detail"),
    path("admin/complaints/<int:pk>/status/", views.admin_update_status, name="admin_update_status"),
]
