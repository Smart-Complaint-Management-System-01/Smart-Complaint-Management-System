from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RegistrationForm


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
