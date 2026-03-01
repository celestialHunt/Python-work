import requests
import json

# Your local server URL
BASE_URL = "http://127.0.0.1:8000"


def test_cancellation():
    url = f"{BASE_URL}/vapi/cancel-appointment"
    
    # Updated payload to match official Vapi Tool Call structure
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCallList": [
                {
                    "id": "tool_cancel_999",
                    "type": "function",
                    "function": {
                        "name": "cancel_appointment",
                        "arguments": {
                            "email": "chitrans.pranav@gmail.com"  # Real email format
                        }
                    }
                }
            ],
            "call": {
                "customer": {
                    "number": "+1234567890" 
                }
            }
        }
    }

    print(f"🗑️ Sending cancellation request for: {payload['message']['toolCallList'][0]['function']['arguments']['email']}")

    try:
        response = requests.post(url, json=payload)
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success! Server processed the tool call.")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❌ Server Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_cancellation()