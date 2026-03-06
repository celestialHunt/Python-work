import requests
import json

# Change this to your local server URL (usually port 8000)
BASE_URL = "http://127.0.0.1:8000"


def test_booking():
    url = f"{BASE_URL}/vapi/book-appointment"
    
    # This payload mimics exactly what Vapi sends when the tool is triggered
    payload = {
        "message": {
            "call": {
                "customer": {
                    "number": "+1234567890"  # Ensure this number exists in your DB!
                }
            },
            "toolCalls": [
                {
                    "id": "tool_12345",
                    "function": {
                        "name": "book_appointment",
                        "arguments": {
                            "name": "John Doe",
                            "email": "not-an-email",
                            "time": "2026-03-01T15:30:00Z"
                        }
                    }
                }
            ]
        }
    }

    print(f"🚀 Sending test booking request to {url}...")

    try:
        response = requests.post(url, json=payload)
        print(f"📡 Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Response from your server:")
            print(json.dumps(response.json(), indent=2))
        else:
            print("❌ Error Response:")
            print(response.text)
  
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the server. Is your FastAPI app running?")

if __name__ == "__main__":
    test_booking()
