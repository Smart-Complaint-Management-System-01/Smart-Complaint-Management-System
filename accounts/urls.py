
from django.urls import path

from config.views import coming_soon
from accounts.views import login_view, logout_view
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required

app_name = "accounts"

urlpatterns = [
    # FR-01 - Pallavi
    path("register/", views.register, name="register"),
    # FR-02 - Prajna
    path("login/", login_view, name="login"),
    # FR-03 - Rakshita
    path("dashboard/", views.dashboard, name="dashboard"),
    # NFR-10 - whole team, later
        # NFR-10 - logout
    path("logout/", login_not_required(auth_views.LogoutView.as_view()), name="logout"),
]
