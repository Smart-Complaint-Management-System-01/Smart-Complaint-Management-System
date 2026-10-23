
from django.urls import path

from config.views import coming_soon
from accounts.views import login_view, logout_view
from . import views

app_name = "accounts"

urlpatterns = [
    # FR-01 - Pallavi
    path("register/", coming_soon, name="register"),
    # FR-02 - Prajna
    path("login/", login_view, name="login"),
    # FR-03 - Rakshita
    path("dashboard/", views.dashboard, name="dashboard"),
    # NFR-10 - whole team, later
    path("logout/", logout_view, name="logout"),
]
