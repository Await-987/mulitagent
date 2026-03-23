"""
ORCA OS View — Flask backend
Run: pip install flask flask-cors
     python demo/os_view/server.py
Then open: http://127.0.0.1:5001 or http://<LAN-IP>:5001
"""
from flask import Flask, jsonify, send_file, request, send_from_directory, abort
from flask_cors import CORS
import json, os, uuid, threading
from urllib.parse import quote
from pathlib import Path
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='/static')
CORS(app)

THIS_DIR   = Path(__file__).parent
DEMO_DIR   = THIS_DIR.parent
ROOT_DIR   = DEMO_DIR.parent
MOCK_DIR   = ROOT_DIR / 'mock_data'
WORK_DIR   = DEMO_DIR / 'working_dir'
IMAGES_DIR = ROOT_DIR / 'images'
OS_VIEW_IMAGE_DIR = THIS_DIR / 'image'
ICON_DIRS = [OS_VIEW_IMAGE_DIR, IMAGES_DIR]

# ── in-memory notification queue ──────────────────────────────────────────
_notifs      = []
_notif_lock  = threading.Lock()

# ── helpers ───────────────────────────────────────────────────────────────
def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def glob_photos():
    d = MOCK_DIR / 'photos'
    files = []
    for ext in ('*.png','*.jpg','*.jpeg','*.gif','*.webp'):
        files += [f.name for f in d.glob(ext)]
    return files

def resolve_photo_url(raw_path):
    if not raw_path:
        return None
    filename = Path(str(raw_path)).name
    if not filename:
        return None
    photo = MOCK_DIR / 'photos' / filename
    if photo.exists():
        return f'/api/photos/file/{quote(filename)}'
    return None

def discover_app_icons():
    icons = {}
    for base_dir in ICON_DIRS:
        if not base_dir.exists():
            continue
        for path in base_dir.rglob('*'):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}:
                continue

            rel = path.relative_to(base_dir).as_posix()
            stem = path.stem.lower()
            variants = {stem}
            if stem.startswith('app_'):
                variants.add(stem[4:])
            if stem.endswith('_icon'):
                variants.add(stem[:-5])

            if base_dir == OS_VIEW_IMAGE_DIR:
                url = f'/api/assets/os-view-images/{quote(rel)}'
            else:
                url = f'/api/assets/images/{quote(rel)}'

            for key in variants:
                icons.setdefault(key, url)
    return icons

def normalize_note(note, fallback_id=None):
    note = note if isinstance(note, dict) else {}
    now = datetime.now().isoformat()
    return {
        'id': note.get('id') or fallback_id or f'note_{uuid.uuid4().hex[:10]}',
        'title': note.get('title', ''),
        'content': note.get('content', ''),
        'created_at': note.get('created_at') or note.get('updated_at') or now,
        'updated_at': note.get('updated_at') or note.get('created_at') or now,
    }

def load_notes():
    path = MOCK_DIR / 'notes' / 'notes_data.json'
    raw = load_json(path) or []
    notes = []
    changed = False

    for idx, item in enumerate(raw):
        normalized = normalize_note(item, fallback_id=f'note_{idx + 1}')
        if normalized != item:
            changed = True
        notes.append(normalized)

    if changed:
        save_json(path, notes)
    return notes

def build_xhs_post_payload(item, source_name=None):
    image_urls = [url for url in (resolve_photo_url(p) for p in item.get('image_paths', [])) if url]
    return {
        **item,
        'id': item.get('id') or source_name,
        'image_urls': image_urls,
    }

# ── static files ──────────────────────────────────────────────────────────
@app.route('/')
def root():
    return send_file(THIS_DIR / 'index.html')

@app.route('/style.css')
def css():
    return send_file(THIS_DIR / 'style.css', mimetype='text/css')

@app.route('/main.js')
def js():
    return send_file(THIS_DIR / 'main.js', mimetype='application/javascript')

@app.route('/api/assets/images/<path:filename>')
def image_asset(filename):
    path = (IMAGES_DIR / filename).resolve()
    if not str(path).startswith(str(IMAGES_DIR.resolve())) or not path.exists():
        abort(404)
    return send_from_directory(str(path.parent), path.name)

@app.route('/api/assets/os-view-images/<path:filename>')
def os_view_image_asset(filename):
    path = (OS_VIEW_IMAGE_DIR / filename).resolve()
    if not str(path).startswith(str(OS_VIEW_IMAGE_DIR.resolve())) or not path.exists():
        abort(404)
    return send_from_directory(str(path.parent), path.name)

@app.route('/api/app-icons')
def api_app_icons():
    return jsonify({'icons': discover_app_icons()})

# ── Soul ──────────────────────────────────────────────────────────────────
@app.route('/api/soul')
def api_soul():
    return jsonify(load_json(MOCK_DIR / 'soul' / 'soul.json') or {})

# ── Contacts ──────────────────────────────────────────────────────────────
@app.route('/api/contacts')
def api_contacts():
    history  = load_json(MOCK_DIR / 'contactors' / 'contactors_data.json') or []
    profiles_raw = load_json(MOCK_DIR / 'contactors' / 'contactors_profiles.json') or [{}]
    profiles = profiles_raw[0] if isinstance(profiles_raw, list) else profiles_raw
    return jsonify({'history': history, 'profiles': profiles})

# ── Notes ─────────────────────────────────────────────────────────────────
@app.route('/api/notes', methods=['GET', 'POST'])
def api_notes():
    path = MOCK_DIR / 'notes' / 'notes_data.json'
    if request.method == 'POST':
        body = request.get_json() or {}
        notes = load_notes()
        if body.get('action') == 'delete':
            note_id = body.get('id')
            notes = [note for note in notes if note.get('id') != note_id]
            save_json(path, notes)
            return jsonify({'ok': True, 'deleted_id': note_id, 'notes': notes})

        note_id = body.get('id') or f'note_{uuid.uuid4().hex[:10]}'
        title = str(body.get('title', '')).strip() or '未命名备忘录'
        content = str(body.get('content', ''))
        now = datetime.now().isoformat()

        saved_note = None
        for note in notes:
            if note.get('id') == note_id:
                note['title'] = title
                note['content'] = content
                note['updated_at'] = now
                saved_note = note
                break

        if saved_note is None:
            saved_note = {
                'id': note_id,
                'title': title,
                'content': content,
                'created_at': now,
                'updated_at': now,
            }
            notes.insert(0, saved_note)

        notes.sort(key=lambda item: item.get('updated_at', ''), reverse=True)
        save_json(path, notes)
        return jsonify({'ok': True, 'note': saved_note, 'notes': notes})

    return jsonify(load_notes())

# ── Photos ────────────────────────────────────────────────────────────────
@app.route('/api/photos')
def api_photos():
    photos_dir = MOCK_DIR / 'photos'
    files      = glob_photos()
    metadata   = load_json(photos_dir / 'photos_data.json') or []

    desc_map = {}
    for item in metadata:
        raw   = item.get('title', '')
        fname = raw.replace('\\', '/').split('/')[-1]
        desc  = item.get('content', {}).get('metadata', fname)
        desc_map[fname] = desc

    result = [{'filename': f, 'url': f'/api/photos/file/{quote(f)}',
               'description': desc_map.get(f, f.replace('.png','').replace('.jpg',''))}
              for f in files]
    return jsonify(result)

@app.route('/api/photos/file/<path:filename>')
def api_photo_file(filename):
    return send_from_directory(str(MOCK_DIR / 'photos'), filename)

# ── 小红书 ────────────────────────────────────────────────────────────────
@app.route('/api/xiaohongshu', methods=['GET', 'POST'])
def api_xhs():
    d = MOCK_DIR / 'xiaohongshu'
    if request.method == 'POST':
        body = request.get_json() or {}
        if body.get('action') == 'delete':
            post_id = Path(str(body.get('id') or '')).name
            if post_id:
                target = d / post_id
                if target.exists() and target.is_file():
                    target.unlink()
            return jsonify({'ok': True, 'deleted_id': post_id})

        title = str(body.get('title', '')).strip() or '未命名笔记'
        text = str(body.get('text', '')).strip()
        image_filenames = body.get('image_filenames') or []

        image_paths = []
        for raw in image_filenames:
            filename = Path(str(raw)).name
            photo_path = MOCK_DIR / 'photos' / filename
            if photo_path.exists():
                image_paths.append(str(photo_path))

        created_at = datetime.now().isoformat()
        file_stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        post = {
            'title': title,
            'text': text,
            'image_paths': image_paths,
            'created_at': created_at,
        }
        filename = f'xhs_post_{file_stamp}.json'
        save_json(d / filename, post)
        return jsonify({'ok': True, 'post': build_xhs_post_payload(post, filename)})

    posts = []
    if d.exists():
        for f in sorted(d.glob('xhs_post_*.json'), reverse=True):
            item = load_json(f)
            if item:
                posts.append(build_xhs_post_payload(item, f.name))
    return jsonify(posts)

# ── 携程 ──────────────────────────────────────────────────────────────────
@app.route('/api/xiecheng')
def api_xiecheng():
    d = MOCK_DIR / 'xiecheng'
    return jsonify({
        'orders':      load_json(d / 'orders.json')      or [],
        'attractions': load_json(d / 'attractions.json') or [],
        'guides':      load_json(d / 'guides.json')      or [],
    })

# ── Documents ─────────────────────────────────────────────────────────────
@app.route('/api/documents')
def api_documents():
    if not WORK_DIR.exists():
        return jsonify({'exists': False, 'files': []})
    files = []
    for item in sorted(WORK_DIR.iterdir()):
        files.append({
            'name':     item.name,
            'is_dir':   item.is_dir(),
            'size':     item.stat().st_size if item.is_file() else None,
            'modified': item.stat().st_mtime,
        })
    return jsonify({'exists': True, 'files': files})

@app.route('/api/documents/file/<path:filename>')
def api_document_file(filename):
    return send_from_directory(str(WORK_DIR), filename)

# ── Search (AIOS hook) ────────────────────────────────────────────────────
@app.route('/api/search', methods=['GET', 'POST'])
def api_search():
    """
    Interface hook for AIOS Search Agent.
    Future: POST query → aios_demo.py Search workflow → stream results.
    """
    if request.method == 'POST':
        body  = request.get_json() or {}
        query = body.get('query', '')
        # TODO: route to ORCA Search Agent
        return jsonify({
            'status':  'mock',
            'query':   query,
            'answer':  (f'**搜索接口预留**\n\n'
                        f'您的问题：{query}\n\n'
                        f'接入 AIOS Search Agent 后将在此显示真实搜索结果。'),
        })
    return jsonify({'status': 'ready'})

# ── Assistant / 小艺 (AIOS hook) ──────────────────────────────────────────
@app.route('/api/assistant', methods=['GET', 'POST'])
def api_assistant():
    """
    Interface hook for 小艺 assistant.
    Future: POST message → Soul Agent → ORCA Workforce → reply.
    Supports aios_demo.py (active) and aios_listener.py (passive) modes.
    """
    if request.method == 'POST':
        body    = request.get_json() or {}
        message = body.get('message', '')
        mode    = body.get('mode', 'active')   # 'active' | 'passive'
        # TODO: route to aios_demo.py / aios_listener.py
        return jsonify({
            'status': 'mock',
            'mode':   mode,
            'reply':  (f'**小艺接口预留**\n\n'
                       f'您说：{message}\n\n'
                       f'接入 AIOS 后小艺将为您服务。'),
        })
    return jsonify({'status': 'ready'})

# ── Notifications ─────────────────────────────────────────────────────────
@app.route('/api/notifications')
def api_notifications():
    """Frontend polls this every 2s. AIOS agents POST to /push."""
    with _notif_lock:
        out = list(_notifs)
        _notifs.clear()
    return jsonify({'notifications': out})

@app.route('/api/notifications/push', methods=['POST'])
def api_push():
    """
    AIOS message.py calls this to surface a notification in the OS.
    Body: { "app": str, "title": str, "message": str }
    """
    body = request.get_json() or {}
    with _notif_lock:
        _notifs.append({
            'id':        str(uuid.uuid4()),
            'app':       body.get('app', 'system'),
            'title':     body.get('title', '通知'),
            'message':   body.get('message', ''),
            'timestamp': datetime.now().isoformat(),
        })
    return jsonify({'ok': True})

# ── Run ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('\nORCA OS View  ->  http://0.0.0.0:5001\n')
    app.run(host='0.0.0.0', debug=True, port=5001, use_reloader=False)
