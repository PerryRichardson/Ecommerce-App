from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import Group
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import SignUpForm

class SignUpView(FormView):
    """Create a user, add to Buyers/Vendors group, log them in."""
    template_name = "accounts/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("core:home")

    def form_valid(self, form):
        user = form.save()
        role = form.cleaned_data["role"]
        group_name = "Vendors" if role == "vendor" else "Buyers"
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        login(self.request, user)
        messages.success(self.request, "Welcome! Your account has been created.")
        return super().form_valid(form)
