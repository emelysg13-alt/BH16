
from django.shortcuts import render


def dashboard(request):
    return render(request, 'panel_admin/dashboard.html')

