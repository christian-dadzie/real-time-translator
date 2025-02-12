from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from googletrans import Translator, LANGUAGES
import io
import pyttsx3
from io import BytesIO
from gtts import gTTS
import os
from flask_login import LoginManager
from auth import auth
from models import db, User
from flask_login import current_user

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

# Initialize the SQLAlchemy instance
db.init_app(app)

# Initialize the LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register the auth blueprint
app.register_blueprint(auth, url_prefix='/auth')

# Initialize Flask-Migrate
migrate = Migrate(app, db)

@app.before_request
def check_login():
    if not current_user.is_authenticated and request.endpoint not in ['auth.login', 'auth.register']:
        return redirect(url_for('auth.login'))

# Mapping between full language names and their codes
LANGUAGE_MAP = {name.capitalize(): code for code, name in LANGUAGES.items()}

@app.route('/')
def index():

    # Initialize TTS engine
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    
    # Create a list of available voices with relevant information
    available_voices = [{'id': voice.id, 'name': voice.name, 'languages': voice.languages} for voice in voices]
    
    return render_template('index.html', language_map=LANGUAGE_MAP, voices=available_voices)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/real_time_translate', methods=['POST'])
def real_time_translate():
    src_lang = request.form['src_lang']
    dest_lang = request.form['dest_lang']
    text = request.form['text']

    if text:
        translator = Translator()
        try:
            translation = translator.translate(
                text,
                src=LANGUAGE_MAP.get(src_lang, 'auto'),
                dest=LANGUAGE_MAP.get(dest_lang, 'en')
            ).text
            return jsonify({'translated_text': translation})
        except Exception as e:
            app.logger.error(f"Translation error: {e}")
            return jsonify({'error': 'Failed to translate text.'}), 500
    return jsonify({'error': 'No text provided.'}), 400

@app.route('/speak', methods=['POST'])
def speak():
    text = request.form['text']
    lang = request.form['lang']
    voice_id = request.form.get('voice_id')
    rate = float(request.form.get('rate', 1))
    pitch = float(request.form.get('pitch', 1))

    if text:
        audio_buffer = synthesize_speech(text, lang, voice_id, rate, pitch)
        if audio_buffer:
            return send_file(audio_buffer, mimetype='audio/mpeg')
        else:
            return jsonify({'error': 'Failed to synthesize speech.'}), 500
    return jsonify({'error': 'No text provided.'}), 400

def synthesize_speech(text, lang, voice_id=None, rate=1.0, pitch=1.0):
    try:
        # Initialize TTS engine
        engine = pyttsx3.init()
        engine.setProperty('rate', int(200 * rate))
        engine.setProperty('pitch', pitch)

        if voice_id:
            engine.setProperty('voice', voice_id)

        # Save to temporary file
        audio_buffer = io.BytesIO()
        temp_file_path = 'temp_audio.mp3'
        engine.save_to_file(text, temp_file_path)
        engine.runAndWait()

        with open(temp_file_path, 'rb') as f:
            audio_buffer.write(f.read())

        # Clean up temporary file
        os.remove(temp_file_path)

        audio_buffer.seek(0)
        return audio_buffer
    except Exception as e:
        app.logger.error(f"Speech synthesis error: {e}")
        return None

@app.route('/play_translation', methods=['POST'])
def play_translation():
    translated_text = request.form.get('translated_text')
    lang = request.form.get('lang')

    if translated_text and lang:
        try:
            tts = gTTS(text=translated_text, lang=LANGUAGE_MAP.get(lang, 'en'))
            audio = BytesIO()
            tts.write_to_fp(audio)
            audio.seek(0)
            
            return send_file(audio, mimetype="audio/mp3", as_attachment=False, download_name="translation.mp3")
        except Exception as e:
            app.logger.error(f"Error during speech synthesis: {e}")
            return jsonify({'error': 'Error during speech synthesis.'}), 500

    return jsonify({'error': 'No translated text or language provided.'}), 400


if __name__ == '__main__':
    app.run(debug=True)
