from twilio.rest import Client
import os

TWILIO_SID = "AC951d8c229c59c72b17634b5f5984c4d6"
TWILIO_AUTH = "e75ae4c11a362b3c92db68aa3993b9bf"
TWILIO_WHATSAPP = "whatsapp:+14155238886"  # Twilio Sandbox
MY_WHATSAPP = "whatsapp:+917676819103"     # Your verified number

client = Client(TWILIO_SID, TWILIO_AUTH)

message = client.messages.create(
    from_=TWILIO_WHATSAPP,
    to=MY_WHATSAPP,
    body="🔥 TEST MESSAGE FROM TWILIO – Are you receiving? 🔥"
)

print("Message SID:", message.sid)
