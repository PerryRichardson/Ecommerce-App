"""Views for the ecommerce app: auth, vendor dashboard, permissions, cart, catalog, reviews, and checkout."""

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ProductForm, ReviewForm, StoreForm
from .models import Order, OrderItem, Product, Review, Store


# ---- Constants ----------------------------------------------------------------

GROUP_VENDORS = "Vendors"
GROUP_BUYERS = "Buyers"


# ---- Helpers ------------------------------------------------------------------

def _get_next_url(request: HttpRequest) -> str:
    """
    Return a safe 'next' URL from POST or GET (empty string if absent/unsafe).
    Prevents open-redirects by restricting to the current host.
    """
    raw = (request.POST.get("next") or request.GET.get("next", "")).strip()
    if raw and url_has_allowed_host_and_scheme(raw, allowed_hosts={request.get_host()}):
        return raw
    return ""


def _is_vendor(user) -> bool:
    """True if the user belongs to the Vendors group."""
    return user.is_authenticated and user.groups.filter(name=GROUP_VENDORS).exists()


def _is_vendor_or_403(user) -> bool:
    """Vendor check that raises 403 instead of redirecting when unauthorized."""
    if _is_vendor(user):
        return True
    raise PermissionDenied


def _get_cart(session) -> dict:
    """
    Return the session-backed cart dict, creating it if missing.
    Structure: {"<product_id>": quantity_int}
    """
    cart = session.get("cart")
    if cart is None:
        cart = {}
        session["cart"] = cart
    return cart


# ---- Auth & Pages --------------------------------------------------------------

def register_user(request: HttpRequest):
    """
    Register a new user as a Buyer or Vendor, log them in, and redirect.

    POST expects: username, password, email (optional), account_type in {'buyer','vendor'}.
    Honors ?next=... to redirect after success.
    """
    next_url = _get_next_url(request)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        email = request.POST.get("email", "").strip()
        account_type = (request.POST.get("account_type") or "").strip().lower()

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect(f"{reverse('ecommerce:register')}?next={next_url}")

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already taken. Please choose another one.")
            return redirect(f"{reverse('ecommerce:register')}?next={next_url}")

        user = User.objects.create_user(username=username, password=password, email=email)

        group_name = GROUP_VENDORS if account_type == "vendor" else GROUP_BUYERS
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            messages.error(request, "Setup error: required group is missing. Please contact support.")
            return redirect(f"{reverse('ecommerce:register')}?next={next_url}")

        user.groups.add(group)
        login(request, user)
        messages.success(request, f"Welcome, {username}! Your account has been created.")
        return redirect(next_url or "ecommerce:welcome")

    return render(request, "register.html", {"next": next_url})


def login_user(request: HttpRequest):
    """
    Authenticate a user and log them in.

    POST expects: username, password.
    Honors ?next=... to redirect after success.
    """
    next_url = _get_next_url(request)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {username}!")
            return redirect(next_url or "ecommerce:welcome")

        messages.error(request, "Invalid username or password.")
        return redirect(f"{reverse('ecommerce:login')}?next={next_url}")

    return render(request, "login.html", {"next": next_url})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def vendor_dashboard(request: HttpRequest):
    """Vendor-only dashboard (403 if not vendor)."""
    return render(request, "vendor_dashboard.html")


@login_required(login_url="ecommerce:login")
def welcome(request: HttpRequest):
    """Welcome page for authenticated users."""
    return render(request, "welcome.html")


def logout_user(request: HttpRequest):
    """Log the user out and redirect to the login page."""
    logout(request)
    return redirect("ecommerce:login")


# ---- Permission-protected View -------------------------------------------------

@login_required(login_url="ecommerce:login")
@permission_required("ecommerce.can_change_product_price", raise_exception=True)
def change_price(request: HttpRequest) -> HttpResponse:
    """Protected page that requires the custom 'can_change_product_price' permission."""
    return render(request, "change_price.html")


# ---- Cart (Sessions) -----------------------------------------------------------

@require_POST
@login_required(login_url="ecommerce:login")
def add_to_cart(request: HttpRequest):
    """
    Add a product to the cart (or increase its quantity).

    POST fields:
      - product_id: int (required)
      - qty: int (optional, defaults to 1; min=1)
    """
    product_id_raw = request.POST.get("product_id", "").strip()
    if not product_id_raw.isdigit():
        messages.error(request, "Invalid product.")
        return redirect("ecommerce:view_cart")

    product_id = int(product_id_raw)
    if not Product.objects.filter(pk=product_id).exists():
        messages.error(request, "Invalid product.")
        return redirect("ecommerce:view_cart")

    try:
        qty = int(request.POST.get("qty", 1))
    except (TypeError, ValueError):
        qty = 1
    if qty < 1:
        qty = 1

    cart = _get_cart(request.session)
    key = str(product_id)
    cart[key] = cart.get(key, 0) + qty

    request.session.modified = True
    messages.success(request, "Added to cart.")
    return redirect("ecommerce:view_cart")


@login_required(login_url="ecommerce:login")
def view_cart(request: HttpRequest):
    """Render the cart with product details and totals."""
    cart = request.session.get("cart", {})
    if not cart:
        return render(request, "cart.html", {"items": [], "total": Decimal("0.00")})

    ids = [int(pid) for pid in cart.keys()]
    products = Product.objects.filter(id__in=ids)

    items: list[dict] = []
    total = Decimal("0.00")
    for product in products:
        qty = int(cart.get(str(product.id), 0))
        subtotal = product.price * qty
        total += subtotal
        items.append({"product": product, "qty": qty, "subtotal": subtotal})

    return render(request, "cart.html", {"items": items, "total": total})


@require_POST
@login_required(login_url="ecommerce:login")
def remove_from_cart(request: HttpRequest, product_id: int):
    """Remove a product from the cart entirely."""
    cart = request.session.get("cart", {})
    key = str(int(product_id))
    if key in cart:
        del cart[key]
        request.session.modified = True
        messages.success(request, "Item removed from cart.")
    else:
        messages.error(request, "Item not found in cart.")
    return redirect("ecommerce:view_cart")


@require_POST
@login_required(login_url="ecommerce:login")
def update_cart_qty(request: HttpRequest, product_id: int):
    """
    Set an explicit quantity for a product in the cart.
    Qty <= 0 removes the item.
    """
    cart = request.session.get("cart", {})
    key = str(int(product_id))

    try:
        qty = int(request.POST.get("qty", 1))
    except (TypeError, ValueError):
        qty = 1

    if qty <= 0:
        if key in cart:
            del cart[key]
            messages.success(request, "Item removed from cart.")
    else:
        cart[key] = qty
        messages.success(request, "Quantity updated.")

    request.session.modified = True
    return redirect("ecommerce:view_cart")


@require_POST
@login_required(login_url="ecommerce:login")
def clear_cart(request: HttpRequest):
    """Remove all items from the cart."""
    if "cart" in request.session:
        del request.session["cart"]
    request.session.modified = True
    messages.success(request, "Cart cleared.")
    return redirect("ecommerce:view_cart")


# ---- STORE CRUD (Vendor-only) --------------------------------------------------

def _own_store_or_404(user, pk):
    """Return store owned by user or 404."""
    return get_object_or_404(Store, pk=pk, vendor=user)


def _own_product_or_404(user, pk):
    """Return product owned by user (via their stores) or 404."""
    return get_object_or_404(Product, pk=pk, store__vendor=user)


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def store_list(request):
    stores = request.user.stores.all()
    return render(request, "vendor/store_list.html", {"stores": stores})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def store_create(request):
    if request.method == "POST":
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save(commit=False)
            store.vendor = request.user
            store.save()
            messages.success(request, "Store created.")
            return redirect("ecommerce:store_list")
    else:
        form = StoreForm()
    return render(request, "vendor/store_form.html", {"form": form, "title": "New Store"})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def store_update(request, pk: int):
    store = _own_store_or_404(request.user, pk)
    if request.method == "POST":
        form = StoreForm(request.POST, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "Store updated.")
            return redirect("ecommerce:store_list")
    else:
        form = StoreForm(instance=store)
    return render(request, "vendor/store_form.html", {"form": form, "title": "Edit Store"})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def store_delete(request, pk: int):
    store = _own_store_or_404(request.user, pk)
    if request.method == "POST":
        store.delete()
        messages.success(request, "Store deleted.")
        return redirect("ecommerce:store_list")
    return render(request, "vendor/confirm_delete.html", {"object": store, "type": "Store"})


# ---- PRODUCT CRUD (Vendor-only) -----------------------------------------------

@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def product_list(request):
    products = Product.objects.filter(store__vendor=request.user).select_related("store")
    return render(request, "vendor/product_list.html", {"products": products})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            if product.store.vendor_id != request.user.id:
                messages.error(request, "Invalid store selection.")
            else:
                product.save()
                messages.success(request, "Product created.")
                return redirect("ecommerce:product_list")
    else:
        form = ProductForm(user=request.user)
    return render(request, "vendor/product_form.html", {"form": form, "title": "New Product"})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def product_update(request, pk: int):
    product = _own_product_or_404(request.user, pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product, user=request.user)
        if form.is_valid():
            p = form.save(commit=False)
            if p.store.vendor_id != request.user.id:
                messages.error(request, "Invalid store selection.")
            else:
                p.save()
                messages.success(request, "Product updated.")
                return redirect("ecommerce:product_list")
    else:
        form = ProductForm(instance=product, user=request.user)
    return render(request, "vendor/product_form.html", {"form": form, "title": "Edit Product"})


@login_required(login_url="ecommerce:login")
@user_passes_test(_is_vendor_or_403)
def product_delete(request, pk: int):
    product = _own_product_or_404(request.user, pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted.")
        return redirect("ecommerce:product_list")
    return render(request, "vendor/confirm_delete.html", {"object": product, "type": "Product"})


# ---- Catalog (Public) ----------------------------------------------------------

def catalog_store_list(request: HttpRequest):
    """Public: show all stores so buyers can browse by store."""
    stores = Store.objects.select_related("vendor").order_by("name")
    return render(request, "catalog/store_list.html", {"stores": stores})


def catalog_product_list(request: HttpRequest, store_id: int):
    """
    Public: list products for a given store.
    Supports simple search with ?q=
    """
    store = get_object_or_404(Store, pk=store_id)
    q = request.GET.get("q", "").strip()

    products = Product.objects.filter(store=store).order_by("name")
    if q:
        products = products.filter(Q(name__icontains=q))

    return render(request, "catalog/product_list.html", {"store": store, "products": products, "q": q})


def catalog_product_detail(request: HttpRequest, pk: int):
    """Public: show a single product, its reviews, and an 'Add to cart' form."""
    product = get_object_or_404(Product.objects.select_related("store"), pk=pk)
    reviews = product.reviews.select_related("user")
    review_form = ReviewForm() if request.user.is_authenticated else None
    return render(request, "catalog/product_detail.html", {"product": product, "reviews": reviews, "review_form": review_form})


# ---- Checkout / Orders ---------------------------------------------------------

@login_required(login_url="ecommerce:login")
def checkout(request: HttpRequest):
    """Confirm checkout page: shows items and a 'Place order' button."""
    cart = request.session.get("cart", {})
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("ecommerce:view_cart")

    ids = [int(pid) for pid in cart.keys()]
    products = Product.objects.filter(id__in=ids)

    items, total = [], Decimal("0.00")
    for product in products:
        qty = int(cart.get(str(product.id), 0))
        subtotal = product.price * qty
        total += subtotal
        items.append({"product": product, "qty": qty, "subtotal": subtotal})

    return render(request, "checkout.html", {"items": items, "total": total})


@require_POST
@login_required(login_url="ecommerce:login")
@transaction.atomic
def place_order(request: HttpRequest):
    """Convert the cart to an Order, decrement stock, email invoice, clear cart."""
    cart = request.session.get("cart", {})
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("ecommerce:view_cart")

    ids = [int(pid) for pid in cart.keys()]
    products = list(Product.objects.select_for_update().filter(id__in=ids))

    total = Decimal("0.00")
    line_items = []
    for p in products:
        qty = int(cart.get(str(p.id), 0))
        if qty <= 0:
            continue
        if p.stock is not None and p.stock < qty:
            messages.error(request, f"Insufficient stock for {p.name}.")
            return redirect("ecommerce:checkout")
        line_total = p.price * qty
        total += line_total
        line_items.append((p, qty, p.price))

    if not line_items:
        messages.error(request, "Your cart has no valid items.")
        return redirect("ecommerce:view_cart")

    order = Order.objects.create(user=request.user, total=total, status="paid")
    for p, qty, price in line_items:
        OrderItem.objects.create(order=order, product=p, qty=qty, price_snapshot=price)
        if p.stock is not None:
            p.stock = max(0, p.stock - qty)
            p.save(update_fields=["stock"])

    if "cart" in request.session:
        del request.session["cart"]
    request.session.modified = True

    subject = f"Invoice for Order #{order.id}"
    body_lines = [f"Thank you for your purchase, {request.user.username}!", "", "Items:"]
    for item in order.items.select_related("product"):
        body_lines.append(f"- {item.product.name} x{item.qty} @ {item.price_snapshot} = {item.line_total()}")
    body_lines.append("")
    body_lines.append(f"Total: {order.total}")
    body = "\n".join(body_lines)

    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@myecom.test"),
        [request.user.email] if request.user.email else [],
        fail_silently=True,  # ok for dev; console backend anyway
    )

    messages.success(request, f"Order #{order.id} placed successfully.")
    return redirect("ecommerce:order_success", order_id=order.id)


@login_required(login_url="ecommerce:login")
def order_success(request: HttpRequest, order_id: int):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__product"),
        pk=order_id,
        user=request.user,
    )
    return render(request, "order_success.html", {"order": order})


# ---- Reviews -------------------------------------------------------------------

@require_POST
@login_required(login_url="ecommerce:login")
def add_review(request: HttpRequest, pk: int):
    """Create a review; mark verified if the user bought the product."""
    product = get_object_or_404(Product, pk=pk)
    form = ReviewForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Please provide a rating between 1 and 5.")
        return redirect("ecommerce:catalog_product_detail", pk=product.id)

    # One review per user+product
    if Review.objects.filter(user=request.user, product=product).exists():
        messages.error(request, "You have already reviewed this product.")
        return redirect("ecommerce:catalog_product_detail", pk=product.id)

    review = form.save(commit=False)
    review.user = request.user
    review.product = product
    review.verified = OrderItem.objects.filter(order__user=request.user, product=product).exists()
    review.save()

    messages.success(request, "Thanks for your review!")
    return redirect("ecommerce:catalog_product_detail", pk=product.id)
