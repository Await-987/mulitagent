"""
ORCA OS View — Flask backend
Run: pip install flask flask-cors
     python demo/os_view/server.py
Then open: http://127.0.0.1:<ORCA_PORT> (default 5001, set ORCA_PORT in .env)
"""
from flask import Flask, jsonify, send_file, request, send_from_directory, abort
from flask_cors import CORS
import json, os, uuid, threading, sys, asyncio
from urllib.parse import quote
from pathlib import Path
from datetime import datetime

# ── Paths (computed early so .env is loaded before PORT is read) ──────────
THIS_DIR = Path(__file__).parent
DEMO_DIR = THIS_DIR.parent
ROOT_DIR = DEMO_DIR.parent

# Load .env from project root so ORCA_PORT (and API keys) are available.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(ROOT_DIR / '.env')
except ImportError:
    pass  # python-dotenv not installed — rely on shell environment

# Pin CAMEL_WORKDIR to demo/working_dir/ so all agents use the correct path
# regardless of the current working directory when server.py is launched.
if 'CAMEL_WORKDIR' not in os.environ:
    os.environ['CAMEL_WORKDIR'] = str(DEMO_DIR / 'working_dir')

# ── Port configuration ────────────────────────────────────────────────────
# To change the port: edit ORCA_PORT in .env (or set the env variable).
PORT = int(os.environ.get('ORCA_PORT', 5001))

app = Flask(__name__, static_folder='.', static_url_path='/static')
CORS(app)

# Make project root importable (for agents/, tools/, demo.os_view, etc.)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ui_bridge lives alongside server.py; fall back to direct import if the
# package path isn't resolved yet (e.g. running as __main__).
try:
    from demo.os_view import ui_bridge as _ui_bridge
except ImportError:
    import ui_bridge as _ui_bridge
MOCK_DIR   = ROOT_DIR / 'mock_data'
WORK_DIR   = DEMO_DIR / 'working_dir'
IMAGES_DIR = ROOT_DIR / 'images'
OS_VIEW_IMAGE_DIR = THIS_DIR / 'image'
ICON_DIRS = [OS_VIEW_IMAGE_DIR, IMAGES_DIR]

# ── in-memory notification queue ──────────────────────────────────────────
_notifs      = []
_notif_lock  = threading.Lock()

# ── search agent sessions ─────────────────────────────────────────────────
_search_sessions      = {}   # session_id → ChatAgent instance
_search_sessions_lock = threading.Lock()

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

@app.route('/lib/<path:filename>')
def lib_asset(filename):
    path = (THIS_DIR / 'lib' / filename).resolve()
    if not str(path).startswith(str((THIS_DIR / 'lib').resolve())) or not path.exists():
        abort(404)
    return send_from_directory(str(path.parent), path.name)

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

# ── Search (AIOS Search Agent) ────────────────────────────────────────────
@app.route('/api/search', methods=['GET', 'POST'])
def api_search():
    if request.method == 'POST':
        body       = request.get_json() or {}
        query      = str(body.get('query', '')).strip()
        session_id = str(body.get('session_id', '')).strip()
        if not query:
            return jsonify({'status': 'error', 'answer': '请输入搜索内容。'})
        if not session_id:
            session_id = str(uuid.uuid4())

        # Lazily create a search agent for this session
        try:
            with _search_sessions_lock:
                if session_id not in _search_sessions:
                    from agents.search_agent import search_agent_factory
                    _search_sessions[session_id] = search_agent_factory()
                agent = _search_sessions[session_id]
        except Exception as e:
            return jsonify({'status': 'error',
                            'answer': f'搜索智能体初始化失败：{e}',
                            'session_id': session_id})

        # Run the async agent step in a fresh event loop
        try:
            result = asyncio.run(agent.astep(query))
            answer = result.msg.content if (result and result.msg) else '未能获取搜索结果。'
            return jsonify({'status': 'ok', 'query': query,
                            'answer': answer, 'session_id': session_id})
        except Exception as e:
            return jsonify({'status': 'error', 'query': query,
                            'answer': f'搜索出错：{e}', 'session_id': session_id})

    return jsonify({'status': 'ready'})


@app.route('/api/search/reset', methods=['POST'])
def api_search_reset():
    body       = request.get_json() or {}
    session_id = str(body.get('session_id', '')).strip()
    with _search_sessions_lock:
        _search_sessions.pop(session_id, None)
    return jsonify({'ok': True})

# ── Assistant / 小艺 (AIOS integration) ──────────────────────────────────────
def _run_aios_task(session_id: str, task_text: str) -> None:
    """Thread target: run the full AIOS pipeline for one 小艺 session."""
    # ContextVars don't propagate to new threads — set explicitly here.
    _ui_bridge.set_session(session_id)
    try:
        from demo.aios_demo import main as _aios_main

        async def _wrapped():
            # Also set inside the coroutine context so asyncio sub-tasks inherit it.
            _ui_bridge.set_session(session_id)
            await _aios_main(task_text)

        asyncio.run(_wrapped())
    except Exception as exc:
        _ui_bridge.push_ai_message(f'❌ 任务执行出错：{exc}')
        _ui_bridge.mark_done()


@app.route('/api/assistant', methods=['GET', 'POST'])
def api_assistant():
    """
    POST {message, session_id?}  → start a new AIOS task in a background thread.
    GET                          → list current sessions.
    """
    if request.method == 'POST':
        body            = request.get_json() or {}
        message         = str(body.get('message', '')).strip()
        session_id      = str(body.get('session_id', '')).strip() or None
        display_sender  = str(body.get('display_sender',  '')).strip()
        display_content = str(body.get('display_content', '')).strip()

        if not message:
            return jsonify({'status': 'error', 'message': '消息不能为空'})

        new_sid = _ui_bridge.create_session(session_id)
        # Push the incoming message directly by session_id (no ContextVar needed).
        if display_content:
            _ui_bridge.push_incoming_display(new_sid, display_sender, display_content)

        t = threading.Thread(
            target=_run_aios_task, args=(new_sid, message), daemon=True
        )
        t.start()
        return jsonify({'status': 'started', 'session_id': new_sid})

    # GET — return list of all sessions
    return jsonify({'status': 'ready', 'sessions': _ui_bridge.list_sessions()})


@app.route('/api/assistant/poll')
def api_assistant_poll():
    """GET ?session_id=xxx&cursor=0  → new messages since cursor."""
    session_id = request.args.get('session_id', '')
    cursor     = int(request.args.get('cursor', '0') or '0')
    return jsonify(_ui_bridge.poll_messages(session_id, cursor))


@app.route('/api/assistant/confirm', methods=['POST'])
def api_assistant_confirm():
    """POST {session_id, answer: true|false}  → unblock a pending confirmation."""
    body       = request.get_json() or {}
    session_id = str(body.get('session_id', '')).strip()
    answer     = bool(body.get('answer', False))
    ok = _ui_bridge.respond_confirm(session_id, answer)
    return jsonify({'ok': ok})


@app.route('/api/assistant/reply', methods=['POST'])
def api_assistant_reply():
    """POST {session_id, text}  → submit a free-text reply to a pending ask."""
    body       = request.get_json() or {}
    session_id = str(body.get('session_id', '')).strip()
    text       = str(body.get('text', '')).strip()
    ok = _ui_bridge.respond_ask(session_id, text)
    return jsonify({'ok': ok})


@app.route('/api/assistant/cancel', methods=['POST'])
def api_assistant_cancel():
    """POST {session_id}  → cancel a running or completed session."""
    body       = request.get_json() or {}
    session_id = str(body.get('session_id', '')).strip()
    _ui_bridge.cancel_session(session_id)
    return jsonify({'ok': True})


@app.route('/api/assistant/sessions')
def api_assistant_sessions():
    """GET → [{id, status}] for all active sessions."""
    return jsonify({'sessions': _ui_bridge.list_sessions()})

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

# ── AIOS Listener (auto-start alongside the web server) ──────────────────
def _start_listener() -> None:
    """Start aios_listener.py as a subprocess so incoming D2D messages are
    handled automatically whenever the OS View server is running."""
    import subprocess, atexit
    listener_script = DEMO_DIR / 'aios_listener.py'
    if not listener_script.exists():
        print('[Listener] aios_listener.py not found — skipping.')
        return
    try:
        proc = subprocess.Popen(
            [sys.executable, str(listener_script)],
            cwd=str(ROOT_DIR),
        )
        atexit.register(lambda: proc.terminate() if proc.poll() is None else None)
        print(f'[Listener] Started (pid {proc.pid})')
    except Exception as exc:
        print(f'[Listener] Failed to start: {exc}')


# ── Run ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import socket as _socket
    _lan_ip = None
    try:
        _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        _lan_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        pass

    _start_listener()

    print('\nORCA OS View')
    print(f'  Local:   http://127.0.0.1:{PORT}')
    if _lan_ip:
        print(f'  Network: http://{_lan_ip}:{PORT}')
    print()
    app.run(host='0.0.0.0', debug=True, port=PORT, use_reloader=False)
