from django.urls import path
from . import views
from django.urls import path
from . import views

app_name = 'donations'

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

"""urlpatterns = [
    path('process/', views.process_donation, name='process_donation'),
    path('<int:donation_id>/process-online/', views.process_online_payment, name='process_online_payment'),
    path('thank-you/', views.donation_thank_you, name='donation_thank_you'),
    path('webhook/<str:gateway>/', views.payment_webhook, name='payment_webhook'),
    
    # Admin views
    path('manual/', views.create_manual_donation, name='create_manual_donation'),
    path('gateway-settings/', views.payment_gateway_settings, name='payment_gateway_settings'),
    path('ussd/process/', views.process_ussd_donation, name='process_ussd_donation'),
    path('ussd/status/<uuid:transaction_id>/', views.check_ussd_status, name='check_ussd_status'),
    path('ussd/webhook/<str:provider>/', views.ussd_webhook, name='ussd_webhook'),
    path('ussd/settings/', views.ussd_provider_settings, name='ussd_provider_settings'),

    # Donation URLs
    path('donation', views.donation_view, name='donation'),
    path('success/', views.donation_success_view, name='donation_success'),
    path('list/', views.donation_list, name='donation_list'),
    path('create/', views.donation_create_view, name='donation_create'),
]"""