from django.urls import path

from . import views

app_name = "complaints"

urlpatterns = [
    # FR-12
    path("notifications/", views.notifications, name="notifications"),

    # FR-05 - Prajna
    path("complaints/", views.my_complaints, name="my_list"),
    # FR-05 - Prajna: View my complaints
    path(
        "complaints/",
        views.my_complaints,
        name="my_list",
    ),

    # FR-04 - Prajna: Complaint submission
    path(
        "complaints/new/",
        views.new_complaint,
        name="new",
    ),
    path(
        "complaints/<str:complaint_id>/submitted/",
        views.submission_confirmation,
        name="submission_confirmation",
    ),

    # FR-08 - Rakshita: Admin complaint management
    path(
        "admin/complaints/",
        views.admin_list,
        name="admin_list",
    ),
    path(
        "admin/complaints/<int:pk>/",
        views.admin_detail,
        name="admin_detail",
    ),
    path(
        "admin/complaints/<int:pk>/status/",
        views.admin_update_status,
        name="admin_update_status",
    ),

    # FR-07 - Prajna: Admin adds an update
    path(
        "admin/complaints/<int:pk>/update/",
        views.admin_add_update,
        name="admin_add_update",
    ),

    # FR-09 - Prajna: Complaint assignment
    path(
        "admin/complaints/<int:pk>/assign/",
        views.admin_assign,
        name="admin_assign",
    ),

    # FR-10: Complaint resolution
    path(
        "admin/complaints/<int:pk>/resolve/",
        views.admin_resolve,
        name="admin_resolve",
    ),

    # FR-06: User complaint details and history
    path(
        "complaints/<str:complaint_id>/",
        views.complaint_detail,
        name="complaint_detail",
    ),
    path(
        "complaints/<str:complaint_id>/history/",
        views.complaint_history,
        name="complaint_history",
    ),

    # FR-06: Admin complaint history
    path(
        "admin/complaints/<int:pk>/history/",
        views.admin_complaint_history,
        name="admin_complaint_history",
    ),

    # FR-07 - Prajna: User adds additional information
    path(
        "complaints/<str:complaint_id>/update/",
        views.add_info,
        name="add_info",
    ),
]