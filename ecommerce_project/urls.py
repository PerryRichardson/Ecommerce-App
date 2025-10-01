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

    # Base site pages (Home, etc.)
    path("", include("core.urls", namespace="core")),

    # Auth: signup / login / logout
    path("accounts/", include("accounts.urls", namespace="accounts")),

    # Catalog (your current app)
    path("shop/", include("catalog.urls", namespace="catalog")),
    # If you still want to keep the old ecommerce app, mount it somewhere else, e.g.:
    # path("legacy/", include("ecommerce.urls")),

    # Password reset flow (uses Django’s default auth templates under /registration/)
    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

  # NEW: API routes
    path("api/", include("api.urls", namespace="api")),

    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
