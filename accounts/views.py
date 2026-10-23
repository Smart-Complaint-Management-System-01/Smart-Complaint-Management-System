from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import RegistrationForm


# ---- FR-01 (Pallavi) ----
@login_not_required
@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error(
                    "email",
                    "An account with this email address or username already exists.",
                )
            else:
                messages.success(
                    request,
                    "Your account has been created successfully.",
                )
                return redirect("accounts:register")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


# ---- FR-02 (Prajna) ----
@login_not_required
def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "You have logged in successfully.")
            next_url = request.POST.get("next") or request.GET.get("next")

            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)

            return redirect("accounts:dashboard")

        messages.error(request, "Invalid email or password.")

    return render(request, "accounts/login.html")


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have logged out successfully.")
    return redirect("home")


# ---- FR-03 (Rakshita) ----
@login_required
def dashboard(request):
    if request.user.is_admin_role:
        return redirect("complaints:admin_list")
    return redirect("complaints:my_list")