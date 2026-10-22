from django.http import HttpResponse


def coming_soon(request, *args, **kwargs):
    """Temporary placeholder; each teammate replaces their route with a real view."""
    return HttpResponse("This page is under construction.", status=501)