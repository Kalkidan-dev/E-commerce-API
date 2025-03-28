from .models import Product, Category, City, Favorite
from .serializers import ProductSerializer, CategorySerializer, FavoriteSerializer, CitySerializer
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet
from django.core.cache import cache
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from ..user.permissions import IsAdminOrOwner
import logging
from rest_framework import filters
import django_filters
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.exceptions import ValidationError, PermissionDenied


class IsAdminOrReadOnly(permissions.BasePermission):
    """Custom permission to allow only admin users to create/edit cities."""

    def has_permission(self, request, view):
        # Read permissions for everyone (GET)
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions (POST, PUT, DELETE) only for admin users
        return request.user and request.user.is_staff

class CityViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get']  # Only allow GET requests (no create/update/delete)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'region']


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing categories, supporting CRUD operations,
    search, filtering, ordering, and bulk operations.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]  # Allow any user for now

    filter_backends = [OrderingFilter, DjangoFilterBackend, SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name']
    ordering_fields = ['name']

    def get_serializer_context(self):
        return {"request": self.request}  # Ensures URLs are generated correctly

    def get_queryset(self):
        """
        Returns categories with caching and optional sorting.
        """
        if self.action in ["list", "retrieve"]:  # Only use caching for GET requests
            sort_by = self.request.query_params.get('sort_by', None)

            # Fetch from cache or DB
            categories = list(Category.objects.all())  # Ensure it's always a list
            if sort_by:
                try:
                    categories = sorted(categories, key=lambda x: getattr(x, sort_by))
                except AttributeError:
                    pass  # Ignore sorting errors

            return Category.objects.filter(id__in=[c.id for c in categories])  # Convert back to queryset

        return super().get_queryset()  # Handle POST, PUT, DELETE properly

    def perform_create(self, serializer):
        serializer.save()  # This ensures the creation of the object

    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def bulk_update(self, request):
        """
        Updates multiple categories at once.
        """
        ids = request.data.get('ids', [])
        name = request.data.get('name')

        if not ids or not name:
            return Response({"detail": "Please provide valid IDs and a name."}, status=status.HTTP_400_BAD_REQUEST)

        categories = Category.objects.filter(id__in=ids)
        if not categories.exists():
            return Response({"detail": "No matching categories found."}, status=status.HTTP_404_NOT_FOUND)

        categories.update(name=name)
        return Response({"detail": "Categories updated successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'], permission_classes=[permissions.IsAdminUser])
    def bulk_delete(self, request):
        """
        Deletes multiple categories at once.
        """
        ids = request.data.get('ids', [])

        if not ids:
            return Response({"detail": "Please provide IDs to delete."}, status=status.HTTP_400_BAD_REQUEST)

        deleted_count, _ = Category.objects.filter(id__in=ids).delete()
        if deleted_count == 0:
            return Response({"detail": "No matching categories found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"detail": f"{deleted_count} categories deleted successfully."}, status=status.HTTP_200_OK)


from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Favorite, Product
from .serializers import FavoriteSerializer

class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only return the authenticated user's favorites"""
        return Favorite.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Add a product to favorites"""
        product_id = request.data.get("product_id")

        if not product_id:
            return Response({"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the product instance
        product = get_object_or_404(Product, id=product_id)

        # Check if already favorited
        if Favorite.objects.filter(user=request.user, product=product).exists():
            return Response({"error": "Product already favorited"}, status=status.HTTP_400_BAD_REQUEST)

        # Create the favorite
        favorite = Favorite.objects.create(user=request.user, product=product)
        return Response(FavoriteSerializer(favorite).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['DELETE'])
    def remove(self, request):
        """Remove a product from favorites"""
        product_id = request.data.get("product_id")

        if not product_id:
            return Response({"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the favorite instance
        favorite = Favorite.objects.filter(user=request.user, product_id=product_id).first()

        if not favorite:
            return Response({"error": "Product not in favorites"}, status=status.HTTP_400_BAD_REQUEST)

        favorite.delete()
        return Response({"message": "Removed from favorites"}, status=status.HTTP_204_NO_CONTENT)


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = django_filters.CharFilter(field_name="category__name", lookup_expr="iexact")

    class Meta:
        model = Product
        fields = ['category', 'min_price', 'max_price']

class ProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProductViewSet(ModelViewSet):
    
    queryset = Product.objects.select_related('category').prefetch_related('images').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]  # For general authentication
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ProductFilter
    filterset_fields = ['category']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']
    search_fields = ['title', 'description']

    def get_serializer_context(self):
        return {"request": self.request}

    def get_queryset(self):
        products = cache.get("products")
        if not products:
            products = Product.objects.all()  # ✅ Don't convert to list
            cache.set("products", products, timeout=60 * 5)
        return products  # ✅ Return QuerySet, not a list


    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(seller=self.request.user, owner=self.request.user)
            cache.delete("products")  # Invalidate cache after creation
        else:
            raise serializer.ValidationError({"error": "Authentication required to create a product."})

    def perform_update(self, serializer):
        if self.request.user == serializer.instance.owner:
            serializer.save()
            cache.delete("products")  # Invalidate cache after update
        else:
            raise serializer.ValidationError({"error": "You are not the owner of this product."})

    def perform_destroy(self, instance):
        instance.delete()
        cache.delete("products")  # Invalidate cache after deletion

class MyListingsViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrOwner]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Product.objects.all()
        if user.role == "vendor":
            return Product.objects.filter(seller=user)
        return Product.objects.none()
