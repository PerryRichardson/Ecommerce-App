from django.views.generic import TemplateView

class HomeView(TemplateView):
    """Simple landing page."""
    template_name = "core/home.html"
