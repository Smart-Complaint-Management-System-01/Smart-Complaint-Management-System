from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required, login_required
from django.shortcuts import redirect

# Create your views here.
# ---- FR-03 (Rakshita) ----
@login_required
def dashboard(request):
    if request.user.is_admin_role:
        return redirect("complaints:admin_list")
    return redirect("complaints:my_list")
