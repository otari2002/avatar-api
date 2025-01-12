from flask import Flask, Response, request,abort
import os
import joblib
import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from flask import Flask
from flask_cors import CORS
import subprocess
from datetime import datetime
from werkzeug.utils import secure_filename
app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173"],  # Your React app's URL
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "expose_headers": ["X-Emotion", "X-Json-Path"],  # Expose custom headers
        "supports_credentials": True
    }
})
# Set environment variables
os.environ["GITHUB_TOKEN"] = "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"



# Load the pre-trained emotion classifier
pipe_lr = joblib.load(open("./models/emotion_classifier_pipe_lr.pkl", "rb"))

# Define file path for audio output
output_file_path = "audio/response.ogg"

emotionMap = {
    "angry": "angry",
    "disgust": "default",
    "fear": "sad",
    "happy": "smile",
    "joy": "smile",
    "neutral": "default",
    "sad": "sad",
    "sadness": "sad",
    "shame": "suprised",
    "surprise": "suprised"
}

# Function to predict emotions
def predict_emotions(docx):
    results = pipe_lr.predict([docx])
    print(results[0])
    return results[0]

# Function to get response from OpenAI
def get_openai_response(input_text,emotion):
    
    emotion_to_tone = {
        "angry": "calm and understanding",
        "disgust": "reassuring and respectful",
        "fear": "supportive and comforting",
        "happy": "enthusiastic and encouraging",
        "joy": "cheerful and engaging",
        "neutral": "informative and neutral",
        "sad": "empathetic and supportive",
        "sadness": "empathetic and supportive",
        "shame": "reassuring and non-judgmental",
        "surprise": "curious and engaged"
    }
    
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=os.environ["GITHUB_TOKEN"],
    )
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant who understands and responds to emotions.",
            },
            {
                "role": "user",
                "content": f'The user seems {emotion}. Respond in a {emotion_to_tone[emotion]} way with no emojis at all. The user said: "{input_text}"',
            }
        ],
        model="gpt-4o",
        temperature=1,
        max_tokens=4096,
        top_p=1
)
    return response.choices[0].message.content

# Function to synthesize speech from text
def synthesize_speech(text):
    speech_key = "B3qfV3snmjam8zaakudkS4Av3YIJTxgBN2zgvbR7LeHZOlfP0WVPJQQJ99BAACYeBjFXJ3w3AAAAACOGGa96"
    service_region = "eastus"

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_config.speech_synthesis_voice_name = "en-US-JasonNeural"
    
    # Configure audio output to be stored in a file
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file_path)
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    
    # Synthesize speech
    result = speech_synthesizer.speak_text_async(text).get()
    
    # Handle speech synthesis result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(f"Speech synthesized successfully and saved to {output_file_path}")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"Speech synthesis canceled: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"Error details: {cancellation_details.error_details}")


def generate_json_from_audio(input_audio_file):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    json_output_file_path = f"results/response_{timestamp}.json"
    os.makedirs("results", exist_ok=True)
    
    # Convert the audio file to Ogg Vorbis format using ffmpeg
    converted_audio_file = f"audio/response_converted_{timestamp}.ogg"
    conversion_command = [
        "ffmpeg", "-i", input_audio_file, "-c:a", "libvorbis", converted_audio_file
    ]
    
    try:
        # Run the conversion command
        print(f"Converting {input_audio_file} to Ogg Vorbis format...")
        conversion_result = subprocess.run(conversion_command, check=True, capture_output=True, text=True)
        print(f"File converted successfully: {conversion_result.stdout}")
        
        # Run the rhubarb command with the converted file
        rhubarb_command = [
            "./Rhubarb/rhubarb",  # Path to rhubarb executable
            "-f", "json", 
            converted_audio_file,
            "-o", json_output_file_path
        ]
        
        # Execute the rhubarb command
        res2 = subprocess.run(rhubarb_command, check=True, capture_output=True, text=True)
        print(f"JSON generated successfully and saved to {json_output_file_path}")
        
        return json_output_file_path
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        print(f"Error message: {e.stderr}")
        raise RuntimeError("Failed to generate JSON from audio.")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("It seems that ffmpeg or Rhubarb is not installed or not found.")
        
# Function to save the audio and predict emotion
def save_audio_and_get_emotion(text):
    userEmotion = "fear" #predict_emotions(text)
    response_text = get_openai_response(text,userEmotion)
    synthesize_speech(response_text)
    json_path=generate_json_from_audio(output_file_path)
    return emotionMap[userEmotion], response_text ,json_path

@app.route("/api/audio", methods=["POST"])
def send_audio_and_emotion():
    input_text = request.json.get("text")  # Get text input from the client
    if not input_text:
        return "Text input is required", 400
    
    # Save audio and get emotion prediction
    emotion, response_text , json_path = save_audio_and_get_emotion(input_text)
   
    def generate_audio():
        with open(output_file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):  # Read file in chunks
                yield chunk  # Yield audio chunk

    return Response(generate_audio(), mimetype="audio/mpeg", headers={"X-Emotion": emotion, "X-Json-Path": json_path})

@app.route("/api/lipSync/<path:filename>", methods=["GET"])
def get_lip_sync_file(filename):
    try:
        filename = secure_filename(os.path.basename(filename))
        
        # Construct the full file path
        file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),  # Get the current directory
            "results",  # results folder
            filename
        )
        
        # Validate the path is within the results directory
        if not os.path.abspath(file_path).startswith(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "results"))
        ):
            abort(403)  # Forbidden if trying to access files outside results directory
        
        # Check if file exists
        if not os.path.exists(file_path):
            return "File not found", 404
            
        # Read and return the file
        with open(file_path, "r") as f:
            json_data = f.read()
        return Response(json_data, mimetype="application/json")
    except FileNotFoundError:
        return "File not found", 404

if __name__ == "__main__":
    app.run(debug=True, port=5000)
