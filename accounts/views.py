
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RegistrationForm


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


# ---- FR-03 (Rakshita) ----
@login_required
def dashboard(request):
    if request.user.is_admin_role:
        return redirect("complaints:admin_list")
    return redirect("complaints:my_list")
