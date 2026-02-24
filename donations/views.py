from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.contrib import messages
import json
import requests
import hashlib
import hmac

from .models import Donation, PaymentGateway
from .forms import DonationForm, CardPaymentForm

def donation_view(request):
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.status = 'pending'
            donation.save()

            if donation.payment_method == 'card':
                # Redirect to card payment page
                return redirect('process_card_payment', reference=donation.reference)
            else:
                # Show bank transfer details
                return redirect('bank_transfer_details', reference=donation.reference)
    else:
        form = DonationForm()

    gateways = PaymentGateway.objects.filter(is_active=True)
    return render(request, 'donations/donation_form.html', {
        'form': form,
        'gateways': gateways
    })

def process_card_payment(request, reference):
    donation = get_object_or_404(Donation, reference=reference)

    if request.method == 'POST':
        card_form = CardPaymentForm(request.POST)
        if card_form.is_valid():
            # Process payment with Paystack (you can use any payment gateway)
            try:
                payment_result = process_paystack_payment(donation, card_form.cleaned_data)

                if payment_result['status']:
                    donation.status = 'completed'
                    donation.authorization_code = payment_result['authorization_code']
                    donation.card_last_four = card_form.cleaned_data['card_number'][-4:]
                    donation.card_type = detect_card_type(card_form.cleaned_data['card_number'])
                    donation.save()

                    return redirect('payment_success', reference=donation.reference)
                else:
                    donation.status = 'failed'
                    donation.save()
                    messages.error(request, f"Payment failed: {payment_result['message']}")

            except Exception as e:
                donation.status = 'failed'
                donation.save()
                messages.error(request, f"Payment processing error: {str(e)}")
    else:
        card_form = CardPaymentForm()

    return render(request, 'donations/card_payment.html', {
        'donation': donation,
        'card_form': card_form,
        'paystack_public_key': getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    })

def bank_transfer_details(request, reference):
    donation = get_object_or_404(Donation, reference=reference)

    # Bank details (you can move this to settings or database)
    bank_details = {
        'bank_name': 'First Bank',
        'account_name': 'Izala Group',
        'account_number': '1234567890',
        'reference': donation.reference,
    }

    if request.method == 'POST':
        # Mark as processing when user confirms they've made transfer
        donation.status = 'processing'
        donation.save()
        messages.success(request, 'Thank you! We will confirm your payment once received.')
        return redirect('payment_pending', reference=donation.reference)

    return render(request, 'donations/bank_transfer.html', {
        'donation': donation,
        'bank_details': bank_details
    })

def payment_success(request, reference):
    donation = get_object_or_404(Donation, reference=reference)
    return render(request, 'donations/payment_success.html', {'donation': donation})

def payment_pending(request, reference):
    donation = get_object_or_404(Donation, reference=reference)
    return render(request, 'donations/payment_pending.html', {'donation': donation})

def payment_status(request, reference):
    donation = get_object_or_404(Donation, reference=reference)
    return JsonResponse({
        'status': donation.status,
        'amount': str(donation.amount),
        'reference': donation.reference
    })

# Payment Gateway Integration
def process_paystack_payment(donation, card_data):
    """Process payment using Paystack"""
    paystack_secret = getattr(settings, 'PAYSTACK_SECRET_KEY', '')

    # Prepare payment data
    payment_data = {
        'email': donation.donor_email or 'donor@example.com',
        'amount': int(donation.amount * 100),  # Convert to kobo
        'reference': donation.reference,
        'metadata': {
            'donor_name': donation.donor_name,
            'donor_phone': donation.donor_phone,
            'purpose': donation.purpose
        }
    }

    # In a real implementation, you would use Paystack's charge endpoint
    # For security, card details should be handled via Paystack.js on frontend
    headers = {
        'Authorization': f'Bearer {paystack_secret}',
        'Content-Type': 'application/json'
    }

    try:
        # This is a simplified version - in production, use proper card tokenization
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            json=payment_data,
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            return {
                'status': data.get('status', False),
                'message': data.get('message', ''),
                'authorization_url': data.get('data', {}).get('authorization_url', ''),
                'access_code': data.get('data', {}).get('access_code', ''),
                'reference': data.get('data', {}).get('reference', '')
            }
        else:
            return {
                'status': False,
                'message': 'Payment initialization failed'
            }

    except Exception as e:
        return {
            'status': False,
            'message': str(e)
        }

def detect_card_type(card_number):
    """Detect card type based on card number"""
    card_number = card_number.replace(' ', '')

    if card_number.startswith('4'):
        return 'visa'
    elif card_number.startswith(('51', '52', '53', '54', '55')):
        return 'mastercard'
    elif card_number.startswith(('34', '37')):
        return 'american_express'
    elif card_number.startswith(('300', '301', '302', '303', '304', '305', '36', '38')):
        return 'diners_club'
    else:
        return 'unknown'

# Webhook Handlers
@csrf_exempt
@require_http_methods(["POST"])
def paystack_webhook(request):
    """Handle Paystack webhook for payment verification"""
    paystack_secret = getattr(settings, 'PAYSTACK_SECRET_KEY', '')

    # Verify webhook signature
    signature = request.headers.get('x-paystack-signature')
    if not signature:
        return HttpResponse(status=400)

    # Verify the signature
    body = request.body
    computed_signature = hmac.new(
        paystack_secret.encode('utf-8'),
        body,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, signature):
        return HttpResponse(status=400)

    # Process the webhook
    try:
        data = json.loads(body)
        event = data.get('event')

        if event == 'charge.success':
            reference = data.get('data', {}).get('reference')

            try:
                donation = Donation.objects.get(reference=reference)
                donation.status = 'completed'
                donation.authorization_code = data.get('data', {}).get('authorization', {}).get('authorization_code')
                donation.save()

                # Send confirmation email (implement email sending logic)
                send_confirmation_email(donation)

            except Donation.DoesNotExist:
                pass

        return JsonResponse({'status': 'success'})

    except json.JSONDecodeError:
        return HttpResponse(status=400)

def send_confirmation_email(donation):
    """Send confirmation email to donor"""
    # Implement email sending logic here
    # You can use Django's send_mail function
    pass

# Admin function to confirm bank transfers
def confirm_bank_transfer(request, reference):
    if not request.user.is_staff:
        return HttpResponse(status=403)

    donation = get_object_or_404(Donation, reference=reference)

    if donation.payment_method == 'transfer' and donation.status == 'processing':
        donation.mark_completed()
        messages.success(request, f'Bank transfer confirmed for {donation.donor_name}')

    return redirect('admin:donations_donation_changelist')