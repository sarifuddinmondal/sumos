
# main.py
import os
import json
import threading
import sys
import webview
import requests
from flask import Flask, render_template, jsonify, request
from supabase import create_client, Client
import pyautogui
import qrcode
from io import BytesIO
import base64
import socket
import re

# --- Firebase Admin Imports ---
import firebase_admin
from firebase_admin import credentials, db

# --- Global Configuration & State ---
APP_VERSION = "1.0.2" 

def get_persistent_data_path():
    """ অ্যাপের ডেটা স্থায়ীভাবে রাখার জন্য পাথ তৈরি """
    app_data_root = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
    path = os.path.join(app_data_root, "SmartOSPro", "userdata")
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path

def get_resource_path(relative_path):
    """ PyInstaller এর জন্য পাথ ম্যানেজমেন্ট """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Paths
TEMPLATE_FOLDER = get_resource_path('templates')
STATIC_ROOT_FOLDER = get_resource_path('static')
SERVICE_ACCOUNT_KEY = get_resource_path('serviceAccountKey.json')

# User Data Paths
USER_DATA_DIR = get_persistent_data_path()
PROFILE_FILE = os.path.join(USER_DATA_DIR, "profile.json")
CHANNELS_DATA_FILE = os.path.join(USER_DATA_DIR, "channels.json")

# --- Firebase Initialization ---
firebase_initialized = False
def initialize_firebase():
    global firebase_initialized
    try:
        if os.path.exists(SERVICE_ACCOUNT_KEY):
            if not firebase_admin._apps:
                cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://sumos-tv-default-rtdb.asia-southeast1.firebasedatabase.app/'
                })
            firebase_initialized = True
            return True
    except: pass
    return False

# --- Supabase Configuration ---
SUPABASE_URL = "https://vkwxheddyagpjbsrovgh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZrd3hoZWRkeWFncGpic3JvdmdoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE0MzY2MSwiZXhwIjoyMDkwNzE5NjYxfQ.Fmo9E773u1NbzXi99VGomTb6NGvM5wBN82aT23gJ-9A"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    supabase = None

TV_USER_AGENT = "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_ROOT_FOLDER)
main_window = None
update_available = False
syncing_status = "Initializing..."

def sync_remote_data():
    global update_available, syncing_status
    if not supabase: 
        syncing_status = "Database Offline"
        return
    try:
        # 1. Version Check
        syncing_status = "Checking for updates..."
        res_ver = supabase.table("app_config").select("value").eq("key", "latest_version").execute()
        if res_ver.data:
            if res_ver.data[0]['value'] != APP_VERSION:
                update_available = True

        # 2. Sync Channel List
        syncing_status = "Syncing channels..."
        res_ch = supabase.table("channels").select("*").execute()
        if res_ch.data:
            with open(CHANNELS_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(res_ch.data, f, indent=4)
        
        syncing_status = "Cloud Sync Active"
    except Exception as e:
        syncing_status = f"Sync Error: {e}"

def get_local_channels():
    if os.path.exists(CHANNELS_DATA_FILE):
        try:
            with open(CHANNELS_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except: IP = '127.0.0.1' 
    finally: s.close()
    return IP

def load_profile():
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {'mobile': None, 'name': 'Guest', 'wallpaper': 'https://picsum.photos/seed/smart-tv/1920/1080'}

def start_firebase_listener():
    profile = load_profile()
    mobile = profile.get('mobile')
    if not mobile or not initialize_firebase(): return
    clean_mobile = re.sub(r'\D', '', str(mobile))
    try:
        ref = db.reference(f'users/{clean_mobile}/remote_control')
        def listener(event):
            if event.data:
                handle_remote_command(str(event.data))
                ref.delete()
        ref.listen(listener)
    except: pass

def handle_remote_command(command):
    if not command or not main_window: return
    parts = str(command).split(',')
    if len(parts) < 2: return
    cat, val = parts[0].strip().lower(), parts[1].strip().upper()
    if cat == "key":
        if val in ["ESC", "HOME", "BACK"]: main_window.load_url("http://127.0.0.1:5000/")
        elif val == "UP": pyautogui.press('up')
        elif val == "DOWN": pyautogui.press('down')
        elif val == "LEFT": pyautogui.press('left')
        elif val == "RIGHT": pyautogui.press('right')
        elif val == "ENTER" or val == "OK": pyautogui.press('enter')
    elif cat == "app":
        if val == "TV": main_window.load_url("http://127.0.0.1:5000/tv")
        elif val == "YOUTUBE": main_window.load_url("https://www.youtube.com/tv")

@app.route('/')
def home_page():
    profile = load_profile()
    local_ip = get_local_ip()
    qr_url = f"https://sumos-tv.web.app/?ip={local_ip}&port=5000&device_id={profile.get('mobile', 'guest')}"
    qr_img = qrcode.make(qr_url)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return render_template('home.html', 
                           profile=profile, 
                           qr_code=qr_b64, 
                           version=APP_VERSION, 
                           update_available=update_available, 
                           sync_msg=syncing_status,
                           wallpaper_url=profile.get('wallpaper'))

@app.route('/tv')
def tv_page(): return render_template('tv.html')

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    mobile = request.json.get('mobile')
    try:
        res = supabase.table("users").select("*").eq("mobile", mobile).execute()
        if res.data:
            user = res.data[0]
            profile_data = {
                'mobile': user['mobile'], 
                'name': user['name'], 
                'state': user['state'], 
                'pin': str(user['pin']), 
                'wallpaper': user.get('wallpaper', 'https://picsum.photos/seed/smart-tv/1920/1080')
            }
            with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=4)
            threading.Thread(target=start_firebase_listener).start()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'User not found'})
    except: return jsonify({'status': 'error', 'message': 'Database error'})

@app.route('/tv/api/channels')
def api_get_channels():
    channels = get_local_channels()
    return jsonify(channels)

@app.route('/logout', methods=['POST'])
def logout():
    if os.path.exists(PROFILE_FILE): os.remove(PROFILE_FILE)
    return jsonify({'status': 'success'})

@app.route('/exit_app', methods=['POST'])
def exit_app():
    if main_window: main_window.destroy()
    else: os._exit(0)
    return jsonify({'status': 'success'})

def setup_app(window):
    global main_window
    main_window = window
    threading.Thread(target=sync_remote_data, daemon=True).start()
    threading.Thread(target=start_firebase_listener, daemon=True).start()

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='127.0.0.1', port=5000), daemon=True).start()
    window = webview.create_window('Smart OS PRO', url="http://127.0.0.1:5000/", fullscreen=True)
    webview.start(setup_app, window, user_agent=TV_USER_AGENT)
