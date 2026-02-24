from django.urls import path
from . import views
from django.urls import path
from . import views


urlpatterns = [
    path('donation', views.donation_view, name='donation'),
    path('process-card/<str:reference>/', views.process_card_payment, name='process_card_payment'),
    path('bank-transfer/<str:reference>/', views.bank_transfer_details, name='bank_transfer_details'),
    path('success/<str:reference>/', views.payment_success, name='payment_success'),
    path('pending/<str:reference>/', views.payment_pending, name='payment_pending'),
    path('status/<str:reference>/', views.payment_status, name='payment_status'),
    path('webhook/paystack/', views.paystack_webhook, name='paystack_webhook'),
    path('admin/confirm-transfer/<str:reference>/', views.confirm_bank_transfer, name='confirm_bank_transfer'),
]