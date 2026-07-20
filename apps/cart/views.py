from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveAPIView, DestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.products.models import ProductVariant
from .models import Cart, CartItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartQuantitySerializer,
)


class CartAddAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddToCartSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        variant = serializer.validated_data['variant']
        quantity = serializer.validated_data['quantity']

        cart, _ = Cart.objects.get_or_create(user=user)

        existing_item = CartItem.objects.filter(cart=cart, variant=variant).first()

        if existing_item:
            new_qty = existing_item.quantity + quantity
            if variant.stock_quantity < new_qty:
                return Response({
                    'success': False,
                    'message': f'Only {variant.stock_quantity} unit(s) available in stock. '
                               f'You already have {existing_item.quantity} in your cart.',
                }, status=status.HTTP_400_BAD_REQUEST)
            existing_item.quantity = new_qty
            existing_item.save()
            item = existing_item
        else:
            item = CartItem.objects.create(
                cart=cart,
                product=variant.product,
                variant=variant,
                quantity=quantity,
                price=variant.price,
                discount_price=variant.discount_price,
            )

        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': 'Product added to cart successfully.',
            'data': cart_serializer.data,
        }, status=status.HTTP_200_OK)


class CartDetailAPIView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

    def retrieve(self, request, *args, **kwargs):
        cart = self.get_object()
        serializer = self.get_serializer(cart)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class CartUpdateQuantityAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateCartQuantitySerializer

    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_item_id = serializer.validated_data['cart_item_id']
        action = serializer.validated_data['action']

        try:
            item = CartItem.objects.get(id=cart_item_id, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cart item not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        if action == 'increase':
            if item.variant.stock_quantity <= item.quantity:
                return Response({
                    'success': False,
                    'message': f'Only {item.variant.stock_quantity} unit(s) available in stock.',
                }, status=status.HTTP_400_BAD_REQUEST)
            item.quantity += 1
            item.save()
        elif action == 'decrease':
            if item.quantity <= 1:
                item.delete()
                cart = Cart.objects.get(user=request.user)
                cart_serializer = CartSerializer(cart, context={'request': request})
                return Response({
                    'success': True,
                    'message': 'Item removed from cart.',
                    'data': cart_serializer.data,
                })
            item.quantity -= 1
            item.save()

        cart = Cart.objects.get(user=request.user)
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': 'Cart updated successfully.',
            'data': cart_serializer.data,
        })


class CartRemoveItemAPIView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        cart_item_id = kwargs.get('cart_item_id')

        try:
            item = CartItem.objects.get(id=cart_item_id, cart__user=request.user)
        except CartItem.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cart item not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        item.delete()

        cart = Cart.objects.get(user=request.user)
        cart_serializer = CartSerializer(cart, context={'request': request})
        return Response({
            'success': True,
            'message': 'Item removed from cart.',
            'data': cart_serializer.data,
        })


class CartClearAPIView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            cart.items.all().delete()
            cart.delete()

        return Response({
            'success': True,
            'message': 'Cart cleared successfully.',
        })
