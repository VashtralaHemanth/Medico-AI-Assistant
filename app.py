from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import pyttsx3
import os
import tempfile

app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key="AIzaSyDHvIXxBSMysTIFxuRIlYrq7SkMAMaRgaA")  # Replace with your actual API key

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Configure voice properties
voices = engine.getProperty('voices')
for voice in voices:
    if "female" in voice.name.lower():
        engine.setProperty('voice', voice.id)
        break

engine.setProperty('rate', 150)
engine.setProperty('volume', 0.9)

def generate_audio(text, filename):
    """Generate audio file from text"""
    engine.save_to_file(text, filename)
    engine.runAndWait()

@app.route('/')
def index():
    return render_template('index.html')

# Store conversation context for each user
user_context = {}

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data.get("user_id", "default")  # Use a user ID to track context
    user_input = data.get("user_input")

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    # Initialize user context if not already done
    if user_id not in user_context:
        user_context[user_id] = {
            "conversation": [],
            "questions_asked": 0
        }

    # Add user input to the conversation history
    user_context[user_id]["conversation"].append(f":User  {user_input}")

    try:
        # Configure Gemini
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=generation_config,
        )

        # Prepare the prompt
        prompt = (
            "You are a medical AI assistant designed to provide guidance on health-related inquiries. "
            "Engage users in a brief, interactive conversation by asking 1–2 relevant questions at a time "
            "to gather key details about their symptoms or concerns. "
            "After approximately three exchanges, provide a concise, informative response with possible causes "
            "and next steps. Keep responses under 120 words, ensuring clarity and relevance. "
            "Do not include 'consult a doctor' each time and do not mention you are AI and you can't predict perfectly.\n"
            + "\n".join(user_context[user_id]["conversation"]) + "\nAI: "
        )

        # Generate content
        response = model.generate_content(prompt)

        # Update conversation history with AI response
        user_context[user_id]["conversation"].append(f"AI: {response.text}")
        user_context[user_id]["questions_asked"] += 1

        # Generate audio file with temporary name
        temp_dir = tempfile.gettempdir()
        audio_file = os.path.join(temp_dir, f"response_{os.urandom(8).hex()}.mp3")
        generate_audio(response.text, audio_file)

        # Check if we need to reset the conversation
        if user_context[user_id]["questions_asked"] >= 3:
            user_context[user_id]["questions_asked"] = 0  # Reset for the next round

        return jsonify({
            "response": response.text,
            "audio_file": os.path.basename(audio_file)
        })

    except Exception as e:
        print(f"Error: {str(e)}")  # Debugging line
        return jsonify({"error": "Failed to generate response"}), 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image part"}), 400

    files = request.files.getlist('image')
    if not files or any(file.filename == '' for file in files):
        return jsonify({"success": False, "error": "No selected files"}), 400

    # Save the files to a temporary location
    temp_dir = tempfile.gettempdir()
    saved_files = []
    for file in files:
        file_path = os.path.join(temp_dir, file.filename)
        file.save(file_path)
        saved_files.append(file_path)

    # Prompt for user input related to the images
    user_input = request.form.get("user_input")
    if not user_input:
        return jsonify({"success": False, "error": "No user input provided"}), 400

    # Use the Gemini model to generate content based on the images and user input
    try:
        # Choose a Gemini model
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

        # Create a prompt
        prompt = f"Reply to this such that you are a medical AI agent and don't say that you are not sure or consult a doctor: {user_input}"

        # Generate content using the images and prompt
        response = model.generate_content(saved_files + [prompt])

        # Generate audio file with temporary name
        audio_file = os.path.join(temp_dir, f"response_{os.urandom(8).hex()}.mp3")
        generate_audio(response.text, audio_file)

        return jsonify({
            "success": True,
            "response": response.text,
            "audio_file": os.path.basename(audio_file)
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"success": False, "error": "Failed to generate response"}), 500

@app.route('/audio/<filename>')
def get_audio(filename):
    try:
        temp_dir = tempfile.gettempdir()
        return send_file(
            os.path.join(temp_dir, filename),
            mimetype='audio/mp3'
        )
    except Exception as e:
        print(f"Error serving audio: {str(e)}")
        return jsonify({"error": "Failed to serve audio"}), 500
    finally:
        # Clean up the temporary file
        try:
            os.remove(os.path.join(temp_dir, filename))
        except:
            pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)