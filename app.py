import os
import uuid
import shutil
import time
import threading
from flask import Flask, render_template, request, jsonify, send_file, abort
from scanner import scan_and_find_duplicates

app = Flask(__name__)

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.tiff', '.tif'}


def cleanup_old_uploads(max_age_seconds=3600):
    """Remove pastas de upload com mais de 1 hora."""
    now = time.time()
    if not os.path.exists(UPLOAD_FOLDER):
        return
    for name in os.listdir(UPLOAD_FOLDER):
        folder = os.path.join(UPLOAD_FOLDER, name)
        if os.path.isdir(folder):
            age = now - os.path.getmtime(folder)
            if age > max_age_seconds:
                shutil.rmtree(folder, ignore_errors=True)


def start_cleanup_thread():
    """Roda limpeza a cada 30 minutos."""
    def loop():
        while True:
            cleanup_old_uploads()
            time.sleep(1800)
    t = threading.Thread(target=loop, daemon=True)
    t.start()


start_cleanup_thread()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    threshold = int(request.form.get('threshold', 10))

    session_id = str(uuid.uuid4())
    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    os.makedirs(session_folder, exist_ok=True)

    saved = 0
    for f in files:
        if not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        safe_name = f"{saved:04d}_{f.filename}"
        f.save(os.path.join(session_folder, safe_name))
        saved += 1

    if saved == 0:
        shutil.rmtree(session_folder, ignore_errors=True)
        return jsonify({'error': 'Nenhuma imagem válida encontrada.'}), 400

    try:
        groups, total_images = scan_and_find_duplicates(session_folder, threshold)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Converter paths absolutos para relativos (session_id/filename)
    for group in groups:
        for img in group:
            img['path'] = os.path.basename(img['path'])

    return jsonify({
        'session_id': session_id,
        'groups': groups,
        'total_images': total_images,
        'total_groups': len(groups),
    })


@app.route('/image/<session_id>/<filename>')
def serve_image(session_id, filename):
    filepath = os.path.join(UPLOAD_FOLDER, session_id, filename)

    # Segurança: impedir path traversal
    real_upload = os.path.realpath(UPLOAD_FOLDER)
    real_file = os.path.realpath(filepath)
    if not real_file.startswith(real_upload):
        abort(403)

    if not os.path.isfile(filepath):
        abort(404)

    return send_file(filepath)


@app.route('/delete', methods=['POST'])
def delete_files():
    data = request.get_json()
    session_id = data.get('session_id', '')
    files = data.get('files', [])

    if not session_id:
        return jsonify({'error': 'session_id ausente.'}), 400

    session_folder = os.path.join(UPLOAD_FOLDER, session_id)
    real_upload = os.path.realpath(UPLOAD_FOLDER)
    real_session = os.path.realpath(session_folder)
    if not real_session.startswith(real_upload):
        abort(403)

    deleted = []
    errors = []

    for filename in files:
        filepath = os.path.join(session_folder, filename)
        real_file = os.path.realpath(filepath)
        if not real_file.startswith(real_session):
            errors.append(f"Caminho inválido: {filename}")
            continue
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
                deleted.append(filename)
            else:
                errors.append(f"Arquivo não encontrado: {filename}")
        except Exception as e:
            errors.append(f"Erro ao deletar {filename}: {str(e)}")

    return jsonify({
        'deleted': deleted,
        'errors': errors,
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
