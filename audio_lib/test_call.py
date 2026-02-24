import requests
import os

API_KEY = None# os.environ["TELNYX_API_KEY"]  # paste your key here

url = "https://api.telnyx.com/v2/calls"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "connection_id": "2901708557156091461",
    "to": "+359884972134",      # your phone
    "from": "+359884972134"     # verified caller ID
}

response = requests.post(url, headers=headers, json=payload)

print(response.status_code)
print(response.text)
