# ecommerce_project/urls.py
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from django.shortcuts import render

# --- Custom 403 handler (PermissionDenied) ---
def permission_denied_view(request, exception):
    return render(request, "403.html", status=403)

# Django looks for these names at module level in the *root* URLconf
handler403 = "ecommerce_project.urls.permission_denied_view"

urlpatterns = [
    path("admin/", admin.site.urls),

    # All site pages (auth, cart, catalog, checkout, reviews, vendor CRUD, etc.)
    # live under the "ecommerce" namespace.
    path("", include(("ecommerce.urls", "ecommerce"), namespace="ecommerce")),

    # API routes
    path("api/", include(("api.urls", "api"), namespace="api")),

    # Password reset flow (Django auth views)
    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
