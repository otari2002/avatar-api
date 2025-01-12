import requests
import os

# URL of the Flask API
API_URL = "http://localhost:5000/api/audio"

# Directory to save the audio file
OUTPUT_DIR = "output_audio"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# File path to save the returned audio
AUDIO_FILE_PATH = os.path.join(OUTPUT_DIR, "response.mp3")

def send_text_and_get_response(text):
    """
    Send text input to the API and get the audio and emotion prediction.
    """
    # Prepare the JSON payload
    payload = {"text": text}
    
    # Send a POST request to the API
    response = requests.post(API_URL, json=payload, stream=True)
    
    # Check if the response is valid
    if response.status_code == 200:
        # Extract emotion and response text from headers
        emotion = response.headers.get("X-Emotion", "Unknown")
        
        # Save the audio file from the response stream
        with open(AUDIO_FILE_PATH, "wb") as audio_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    audio_file.write(chunk)
        
        print(f"Emotion predicted: {emotion}")
        print(f"Audio saved to: {AUDIO_FILE_PATH}")
        
        # Play the audio
        print("Playing the audio...")
        # playsound(AUDIO_FILE_PATH)
    else:
        print(f"Error: {response.status_code}, {response.text}")

if __name__ == "__main__":
    # User input text
    input_text = input("Enter your text: ")
    send_text_and_get_response(input_text)
