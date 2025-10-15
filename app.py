import os
import json
import re
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import datetime

load_dotenv()

app = Flask(__name__)

HISTORY_FILE = 'history.json'

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
except KeyError:
    print("🔴 GEMINI_API_KEY not found. Please set it in your .env file.")
    model = None
except Exception as e:
    print(f"🔴 An error occurred during Gemini API configuration: {e}")
    model = None

SYSTEM_PROMPT = """
You are an AI assistant for a symptom checker application. Your role is to provide a structured analysis of user-described symptoms, taking into account their age and gender for a more accurate assessment.

IMPORTANT: You are not a medical professional. Your suggestions are for informational and educational purposes only and should not be considered a substitute for professional medical advice, diagnosis, or treatment.

When a user provides their symptoms, age, and gender, you MUST structure your response using the following headings and format EXACTLY. Do not add any other text before the first heading or after the last one.

### GIVEN SYMPTOMS
- [Summarize the user's symptoms here in a bulleted list.]

### POSSIBLE CAUSES
- **[Condition 1]:** [Description of the condition, considering the user's age and gender.]
- **[Condition 2]:** [Description of the condition, considering the user's age and gender.]
- **[Condition 3]:** [Description of the condition, considering the user's age and gender.]

### CURE
- **Disclaimer: Do not take any medication without consulting a doctor. The suggestions below are for informational purposes and are not prescriptions.**
- **For [Condition 1]:** [Suggest potential no-risk medication or treatment and include important cautions.]
- **For [Condition 2]:** [Suggest potential no-risk medication or treatment and include important cautions.]

### PRECAUTIONS OR PREVENTIONS
- [Precaution or prevention tip 1]
- [Precaution or prevention tip 2]
- [Precaution or prevention tip 3]

### EXPERT ADVICE
- **Disclaimer:** This information is for educational purposes only. Always consult a doctor for any health concerns.
- [Next step 1, which must always be to consult a healthcare professional.]
- [Next step 2]

### EMERGENCY LEVEL
- **[Low/Medium/High/Critical]:** [Provide a one-sentence justification for the assigned level, taking age and gender into account.]
"""

def parse_gemini_response(text):
    sections = {
        "given_symptoms": "No information provided.",
        "possible_causes": "No information provided.",
        "cure": "No information provided.",
        "precautions_or_preventions": "No information provided.",
        "expert_advice": "No information provided.",
        "emergency_level": "No information provided."
    }
    pattern = r"###\s(.*?)\n(.*?)(?=\n###\s|$)"
    matches = re.findall(pattern, text, re.DOTALL)
    for header, content in matches:
        header = header.strip().upper()
        content = content.strip()
        if "GIVEN SYMPTOMS" in header:
            sections["given_symptoms"] = content
        elif "POSSIBLE CAUSES" in header:
            sections["possible_causes"] = content
        elif "CURE" in header:
            sections["cure"] = content
        elif "PRECAUTIONS OR PREVENTIONS" in header:
            sections["precautions_or_preventions"] = content
        elif "EXPERT ADVICE" in header:
            sections["expert_advice"] = content
        elif "EMERGENCY LEVEL" in header:
            sections["emergency_level"] = content
    return sections

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_symptoms', methods=['POST'])
def check_symptoms():
    if not model:
        return jsonify({"error": "Gemini API is not configured. Please check server logs."}), 500
    data = request.get_json()
    if not data or 'symptoms' not in data or 'age' not in data or 'gender' not in data:
        return jsonify({"error": "Invalid input. 'symptoms', 'age', and 'gender' fields are required."}), 400
    
    user_symptoms = data['symptoms']
    user_age = data['age']
    user_gender = data['gender']

    if not user_symptoms.strip() or not user_age or not user_gender:
        return jsonify({"error": "All fields are required."}), 400
        
    try:
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser's Age: {user_age}\nUser's Gender: {user_gender}\nUser's Symptoms: {user_symptoms}"
        response = model.generate_content(full_prompt)
        result_text = response.text
        parsed_result = parse_gemini_response(result_text)
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []
        history.insert(0, {
            'symptoms': user_symptoms,
            'age': user_age,
            'gender': user_gender,
            'analysis': parsed_result,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=4)
        return jsonify(parsed_result)
    except Exception as e:
        print(f"🔴 An error occurred while processing your request: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    return jsonify(history)

if __name__ == '__main__':
    app.run(debug=True)

