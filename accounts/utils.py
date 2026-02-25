import requests

def send_jibwis_sms(phone_number, message):
    url = "https://api.ng.termii.com/api/sms/send"
    payload = {
        "to": phone_number,
        "from": "JIBWIS", # This is your registered Sender ID
        "sms": message,
        "type": "plain",
        "channel": "generic", # Use 'dnd' for members with DND active
        "api_key": "YOUR_TERMII_API_KEY",
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except Exception as e:
        return None