from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.categories.models import Category
from apps.common.permissions import IsAdminUser
from apps.orders.models import Order, OrderItem
from apps.products.models import Product, ProductVariant
from apps.repairs.models import RepairTicket
from apps.tradeins.models import TradeIn

User = get_user_model()

ZERO = Value(Decimal('0'))
OPEN_ORDER_STATUSES = ('order_placed', 'accepted', 'processing', 'shipped', 'out_for_delivery')
CLOSED_REPAIR_STATUSES = ('completed', 'cancelled', 'rejected')


def _money(value):
    return float(value or 0)


def _growth(current, previous):
    current, previous = float(current or 0), float(previous or 0)
    if previous == 0:
        # No baseline: a percentage would be meaningless, so let the UI say so.
        return None
    return round((current - previous) / previous * 100, 1)


def _customers():
    """Shopper accounts: everything that is not an admin account."""
    return User.objects.filter(is_staff=False, is_superuser=False).exclude(role__in=('admin', 'superadmin'))


class DashboardAPIView(GenericAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.localtime()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today.replace(day=1)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        yesterday = today - timedelta(days=1)

        sales = Order.objects.exclude(order_status='cancelled')

        def revenue(qs):
            return qs.aggregate(v=Coalesce(Sum('grand_total'), ZERO))['v']

        today_sales = revenue(sales.filter(created_at__gte=today))
        yesterday_sales = revenue(sales.filter(created_at__gte=yesterday, created_at__lt=today))
        month_revenue = revenue(sales.filter(created_at__gte=month_start))
        prev_month_revenue = revenue(sales.filter(created_at__gte=prev_month_start, created_at__lt=month_start))

        variants = ProductVariant.objects.filter(is_active=True, product__is_published=True)
        low_stock_qs = variants.filter(stock_quantity__lte=F('low_stock_alert'))

        repairs = RepairTicket.objects.all()
        open_repairs = repairs.exclude(status__in=CLOSED_REPAIR_STATUSES)
        customers = _customers()

        kpis = {
            'todaySales': _money(today_sales),
            'todaySalesGrowth': _growth(today_sales, yesterday_sales),
            'monthRevenue': _money(month_revenue),
            'monthRevenueGrowth': _growth(month_revenue, prev_month_revenue),
            'ordersTotal': Order.objects.count(),
            'ordersOpen': Order.objects.filter(order_status__in=OPEN_ORDER_STATUSES).count(),
            'ordersToday': Order.objects.filter(created_at__gte=today).count(),
            'repairsOpen': open_repairs.count(),
            'repairsUrgent': open_repairs.filter(priority__in=('high', 'urgent')).count(),
            'repairsToday': repairs.filter(created_at__gte=today).count(),
            'repairsReady': repairs.filter(status='ready_for_pickup').count(),
            'customersTotal': customers.count(),
            'customersNewThisMonth': customers.filter(date_joined__gte=month_start).count(),
            'productsPublished': Product.objects.filter(is_published=True).count(),
            'stockUnits': variants.aggregate(v=Coalesce(Sum('stock_quantity'), 0))['v'],
            'lowStockCount': low_stock_qs.count(),
            'outOfStockCount': variants.filter(stock_quantity=0).count(),
            'tradeInsPending': TradeIn.objects.filter(status__in=('pending', 'reviewed')).count(),
        }

        start_14 = today - timedelta(days=13)
        daily = {
            row['day']: row
            for row in sales.filter(created_at__gte=start_14)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(revenue=Sum('grand_total'), orders=Count('id'))
        }
        sales_trend = []
        for i in range(14):
            day = (start_14 + timedelta(days=i)).date()
            row = daily.get(day, {})
            sales_trend.append({
                'date': day.isoformat(),
                'revenue': _money(row.get('revenue')),
                'orders': row.get('orders', 0),
            })

        six_months_ago = month_start
        for _ in range(5):
            six_months_ago = (six_months_ago - timedelta(days=1)).replace(day=1)
        monthly = {
            row['month'].date() if hasattr(row['month'], 'date') else row['month']: row
            for row in sales.filter(created_at__gte=six_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(revenue=Sum('grand_total'), orders=Count('id'))
        }
        revenue_trend = []
        cursor = six_months_ago
        for _ in range(6):
            row = monthly.get(cursor.date(), {})
            revenue_trend.append({
                'month': cursor.strftime('%b'),
                'revenue': _money(row.get('revenue')),
                'orders': row.get('orders', 0),
            })
            cursor = (cursor + timedelta(days=32)).replace(day=1)

        orders_by_status = [
            {'status': key, 'label': label, 'count': 0} for key, label in Order.ORDER_STATUS
        ]
        counts = dict(Order.objects.values_list('order_status').annotate(c=Count('id')))
        for row in orders_by_status:
            row['count'] = counts.get(row['status'], 0)

        repair_counts = dict(repairs.values_list('status').annotate(c=Count('id')))
        repairs_by_status = [
            {'status': key, 'label': label, 'count': repair_counts.get(key, 0)}
            for key, label in RepairTicket.STATUS_CHOICES
            if repair_counts.get(key)
        ]

        categories = list(
            Category.objects.annotate(product_count=Count('products', filter=Q(products__is_published=True)))
            .filter(product_count__gt=0)
            .order_by('-product_count')
            .values('category_name', 'product_count')[:6]
        )

        top_products = list(
            OrderItem.objects.exclude(order__order_status='cancelled')
            .values('product_name')
            .annotate(units=Sum('quantity'), revenue=Sum('total_price'))
            .order_by('-units')[:5]
        )
        for row in top_products:
            row['revenue'] = _money(row['revenue'])

        low_stock = [
            {
                'id': v.id,
                'product': v.product.product_name,
                'variant': v.variant_name,
                'stock': v.stock_quantity,
                'threshold': v.low_stock_alert,
            }
            for v in low_stock_qs.select_related('product').order_by('stock_quantity')[:6]
        ]

        recent_orders = [
            {
                'orderNumber': o.order_number,
                'customer': o.user.get_full_name() or o.user.email,
                'total': _money(o.grand_total),
                'status': o.order_status,
                'statusLabel': o.get_order_status_display(),
                'paymentStatus': o.payment_status,
                'createdAt': o.created_at.isoformat(),
            }
            for o in Order.objects.select_related('user').order_by('-created_at')[:6]
        ]

        recent_repairs = [
            {
                'id': t.id,
                'ticketNumber': t.ticket_number,
                'customer': t.customer_name,
                'device': f'{t.device_brand} {t.device_model}'.strip(),
                'status': t.status,
                'statusLabel': t.get_status_display(),
                'priority': t.priority,
                'createdAt': t.created_at.isoformat(),
            }
            for t in repairs.order_by('-created_at')[:6]
        ]

        return Response({
            'success': True,
            'data': {
                'generatedAt': now.isoformat(),
                'kpis': kpis,
                'salesTrend': sales_trend,
                'revenueTrend': revenue_trend,
                'ordersByStatus': orders_by_status,
                'repairsByStatus': repairs_by_status,
                'categories': [{'name': c['category_name'], 'products': c['product_count']} for c in categories],
                'topProducts': [
                    {'name': r['product_name'], 'units': r['units'], 'revenue': r['revenue']} for r in top_products
                ],
                'lowStock': low_stock,
                'recentOrders': recent_orders,
                'recentRepairs': recent_repairs,
            },
        })


def _customer_row(user):
    return {
        'id': user.id,
        'name': user.get_full_name(),
        'email': user.email,
        'mobile': user.mobile_number or '',
        'isActive': user.is_active,
        'isVerified': user.is_verified,
        'dateJoined': user.date_joined.isoformat(),
        'ordersCount': user.orders_count,
        'totalSpent': _money(user.total_spent),
        'repairsCount': user.repairs_count,
        'lastOrderAt': user.last_order_at.isoformat() if user.last_order_at else None,
    }


def _annotated_customers():
    return _customers().annotate(
        orders_count=Count('orders', distinct=True),
        total_spent=Coalesce(
            Sum('orders__grand_total', filter=~Q(orders__order_status='cancelled')), ZERO
        ),
        repairs_count=Count('repair_tickets', distinct=True),
        last_order_at=Max('orders__created_at'),
    )


class CustomerListAPIView(GenericAPIView):
    permission_classes = [IsAdminUser]

    SORTS = {
        'newest': '-date_joined',
        'oldest': 'date_joined',
        'spent': '-total_spent',
        'orders': '-orders_count',
        'name': 'first_name',
    }

    def get(self, request):
        qs = _annotated_customers()
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
                | Q(email__icontains=search) | Q(mobile_number__icontains=search)
            )
        state = request.query_params.get('status', '').strip()
        if state == 'active':
            qs = qs.filter(is_active=True)
        elif state == 'inactive':
            qs = qs.filter(is_active=False)

        qs = qs.order_by(self.SORTS.get(request.query_params.get('sort', ''), '-date_joined'), '-id')

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
            page_size = min(max(int(request.query_params.get('page_size', 20)), 1), 100)
        except ValueError:
            return Response(
                {'success': False, 'message': 'page and page_size must be whole numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total = qs.count()
        rows = qs[(page - 1) * page_size: page * page_size]
        base = _customers()
        return Response({
            'success': True,
            'data': {
                'results': [_customer_row(u) for u in rows],
                'count': total,
                'page': page,
                'pageSize': page_size,
                'summary': {
                    'total': base.count(),
                    'active': base.filter(is_active=True).count(),
                    'newThisMonth': base.filter(
                        date_joined__gte=timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    ).count(),
                    'withOrders': base.filter(orders__isnull=False).distinct().count(),
                },
            },
        })


class CustomerStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class CustomerDetailAPIView(GenericAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = CustomerStatusSerializer

    def _get(self, pk):
        return _annotated_customers().filter(pk=pk).first()

    def get(self, request, pk):
        user = self._get(pk)
        if not user:
            return Response({'success': False, 'message': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = _customer_row(user)
        data['addresses'] = [
            {
                'id': a.id,
                'fullName': a.full_name,
                'mobile': a.mobile_number,
                'line': ', '.join(p for p in [a.house_number, a.street_address, a.landmark] if p),
                'city': a.city,
                'state': a.state,
                'pincode': a.pincode,
                'type': a.address_type,
                'isDefault': a.is_default,
            }
            for a in user.addresses.all()
        ]
        data['orders'] = [
            {
                'orderNumber': o.order_number,
                'total': _money(o.grand_total),
                'status': o.order_status,
                'statusLabel': o.get_order_status_display(),
                'paymentStatus': o.payment_status,
                'items': o.items.count(),
                'createdAt': o.created_at.isoformat(),
            }
            for o in user.orders.order_by('-created_at')[:10]
        ]
        data['repairs'] = [
            {
                'id': t.id,
                'ticketNumber': t.ticket_number,
                'device': f'{t.device_brand} {t.device_model}'.strip(),
                'status': t.status,
                'statusLabel': t.get_status_display(),
                'createdAt': t.created_at.isoformat(),
            }
            for t in user.repair_tickets.order_by('-created_at')[:10]
        ]
        return Response({'success': True, 'data': data})

    def patch(self, request, pk):
        user = self._get(pk)
        if not user:
            return Response({'success': False, 'message': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CustomerStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.is_active = serializer.validated_data['is_active']
        user.save(update_fields=['is_active'])
        user = self._get(pk)
        return Response({
            'success': True,
            'message': 'Customer activated.' if user.is_active else 'Customer deactivated.',
            'data': _customer_row(user),
        })
