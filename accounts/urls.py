from django.urls import path

from config.views import coming_soon

from . import views

app_name = "accounts"

urlpatterns = [
    # FR-01 - Pallavi
    path("register/", views.register, name="register"),
    # FR-02 - Prajna
    path("login/", coming_soon, name="login"),
    # NFR-10 - 
    path("logout/", coming_soon, name="logout"),
]
