from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from complaints.models import Complaint


def my_list(request):
    Complaint.objects.select_related("user").all()[:10]
    return HttpResponse("My complaints")


def new_complaint(request):
    return HttpResponse("New complaint")


def admin_list(request):
    Complaint.objects.select_related("user").all()[:10]
    return HttpResponse("Admin complaint list")


def admin_detail(request, pk):
    complaint = get_object_or_404(Complaint.objects.select_related("user"), pk=pk)
    return HttpResponse(f"Complaint detail: {complaint.title}")
