from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class SignUpForm(UserCreationForm):
    """User sign-up with email and role (buyer/vendor)."""
    ROLE_CHOICES = [("buyer", "Buyer"), ("vendor", "Vendor")]

    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ("username", "email", "role", "password1", "password2")
