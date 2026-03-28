import requests
from django.conf import settings

def verify_bank_account(account_number, bank_code):
    """
    Verifies a Nigerian bank account using Paystack API.
    Returns the account name if successful, else None.
    """
    # Replace 'YOUR_PAYSTACK_SECRET_KEY' with your actual key in settings.py
    url = f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('status') is True:
            # Returns the full name registered to the bank account
            return data['data']['account_name']
    except Exception as e:
        print(f"Error verifying bank account: {e}")
    
    return None