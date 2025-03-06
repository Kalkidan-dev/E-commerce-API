from django.db import models
from django.conf import settings
from core.product.models import Product  # Import Product from the product app

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart for {self.user.first_name}"

    def total_price(self):
        """Calculate the total price of all items in the cart"""
        return sum(item.total_price() for item in self.cart_items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='cart_items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in cart"

    def total_price(self):
        """Calculate the total price for this cart item"""
        return self.product.price * self.quantity
