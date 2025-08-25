from django.http import HttpResponse

def index(request):
    return HttpResponse("Catalog app is wired up correctly.")
