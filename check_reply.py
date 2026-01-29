import requests
import xml.etree.ElementTree as ET

url = "https://my-leads.app/webhooks/whatsapp/twilio"

payload = {
    "From": "whatsapp:+972501234567",
    "Body": "היי מאמי, אני לא מרגישה טוב, חייבת לבטל את השיעור של מחר",
    "NumMedia": "0"
}

print("🚀 שולח הודעה לשרת...")
response = requests.post(url, data=payload)

if response.status_code == 200:
    # מפענח את ה-XML
    root = ET.fromstring(response.text)
    message = root.find("Message").text
    print("\n✅ התשובה שהתקבלה מה-AI:")
    print("------------------------------------------------")
    print(f"🤖 {message}")
    print("------------------------------------------------")
else:
    print(f"❌ שגיאה: {response.status_code}")
    print(response.text)
