# ecommerce/forms.py
from django import forms
from .models import Store, Product
from .models import Review


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ("name", "description")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ("store", "name", "price", "stock")

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Limit the store dropdown to the current vendor’s stores
        if user is not None:
            self.fields["store"].queryset = user.stores.all()

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {
            "rating": forms.NumberInput(attrs={"min": 1, "max": 5}),
            "comment": forms.Textarea(attrs={"rows": 3}),
        }