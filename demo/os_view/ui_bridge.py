"""
UI Bridge — connects AIOS backend tools/agents to the OS View frontend.

Provides session management, message streaming, and user confirmation.
Each AIOS task run gets a unique session ID. The frontend polls for
messages and responds to confirmation requests via Flask API endpoints.

ContextVar propagation: Python 3.7+ copies the current context into
asyncio sub-tasks and into executor threads (run_in_executor), so the
session ID flows transparently through the entire CAMEL workforce.
"""
import threading
import contextvars
import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# Context variable — survives asyncio task hops and executor threads
# ---------------------------------------------------------------------------
_session_id_var: contextvars.ContextVar = contextvars.ContextVar(
    'aios_session_id', default=None
)

_sessions: dict = {}   # session_id → session dict
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def create_session(session_id: Optional[str] = None) -> str:
    """Create a new session, bind it to the current context, return its ID."""
    if not session_id:
        session_id = uuid.uuid4().hex[:12]
    with _lock:
        _sessions[session_id] = {
            'status': 'running',     # 'running' | 'done'
            'messages': [],          # list of message dicts
            'pending_confirm': None, # {id, event, result} while waiting for Yes/No
            'pending_ask': None,     # {id, event, result} while waiting for text reply
            'cancelled': False,      # True after cancel_session() is called
        }
    _session_id_var.set(session_id)
    return session_id


def set_session(session_id: str) -> None:
    """Bind an existing session to the current execution context."""
    _session_id_var.set(session_id)


def get_session_id() -> Optional[str]:
    return _session_id_var.get()


# ---------------------------------------------------------------------------
# Message pushing  (called from tools / aios_demo.py)
# ---------------------------------------------------------------------------

def push_system_message(text: str) -> None:
    """Centered status label in 小艺 chat (WeChat-style timestamp line)."""
    sid = _session_id_var.get()
    if not sid:
        return
    with _lock:
        s = _sessions.get(sid)
        if s and not s.get('cancelled'):
            s['messages'].append({'type': 'system', 'text': text})


def push_ai_message(text: str) -> None:
    """AI chat bubble in 小艺 chat."""
    sid = _session_id_var.get()
    if not sid:
        return
    with _lock:
        s = _sessions.get(sid)
        if s and not s.get('cancelled'):
            s['messages'].append({'type': 'ai', 'text': text})


def mark_done(result: Optional[str] = None) -> None:
    """Mark session finished. Optional final AI message."""
    sid = _session_id_var.get()
    if not sid:
        return
    with _lock:
        s = _sessions.get(sid)
        if s and not s.get('cancelled'):
            if result:
                s['messages'].append({'type': 'ai', 'text': result})
            s['status'] = 'done'


# ---------------------------------------------------------------------------
# Confirmation gate  (called from tools, blocks the calling thread)
# ---------------------------------------------------------------------------

def request_confirm(prompt: str, details: Optional[str] = None,
                    extras: Optional[dict] = None) -> bool:
    """
    Request yes/no confirmation via the phone UI.
    Blocks until the user responds (max 5 min) or falls back to console.

    Args:
        prompt: Title text shown in the confirm dialog.
        details: Secondary detail text.
        extras: Optional dict with extra data for the frontend (e.g.
                ``{'images': ['/api/photos/file/a.jpg', ...]}``).

    Returns True for yes / False for no/timeout.
    """
    sid = _session_id_var.get()
    if not sid:
        answer = input(f"{prompt} (yes/no): ").strip().lower()
        return answer in ('yes', 'y')

    confirm_id = uuid.uuid4().hex[:8]
    event = threading.Event()
    result_box: list = [None]   # [True | False | None]

    with _lock:
        s = _sessions.get(sid)
        if not s:
            answer = input(f"{prompt} (yes/no): ").strip().lower()
            return answer in ('yes', 'y')
        # If the session is already done or cancelled, skip the dialog silently.
        if s.get('cancelled') or s.get('status') == 'done':
            return False
        msg = {
            'type': 'confirm',
            'id': confirm_id,
            'prompt': prompt,
            'details': details,
        }
        if extras:
            msg['extras'] = extras
        s['messages'].append(msg)
        s['pending_confirm'] = {
            'id': confirm_id,
            'event': event,
            'result': result_box,
        }

    event.wait(timeout=300)   # 5-minute safety timeout

    with _lock:
        s = _sessions.get(sid)
        if s and (s.get('pending_confirm') or {}).get('id') == confirm_id:
            s['pending_confirm'] = None

    return result_box[0] is True


def respond_confirm(session_id: str, answer: bool) -> bool:
    """Called by the server /api/assistant/confirm when user taps Yes/No."""
    with _lock:
        s = _sessions.get(session_id)
        if not s:
            return False
        pending = s.get('pending_confirm')
        if not pending:
            return False
        pending['result'][0] = answer
        pending['event'].set()
    return True


# ---------------------------------------------------------------------------
# Free-text ask gate  (called from tools, blocks the calling thread)
# ---------------------------------------------------------------------------

def ask_user_for_session(sid: str, question: str, timeout: float = 300.0) -> str:
    """Like :func:`ask_user` but with explicit session id.

    Used when the caller is not in the request ContextVar (e.g. an IPC
    endpoint serving the Hermes subprocess bridge).
    """
    if not sid:
        return ''

    ask_id = uuid.uuid4().hex[:8]
    event = threading.Event()
    result_box: list = [None]

    with _lock:
        s = _sessions.get(sid)
        if not s:
            return ''
        if s.get('cancelled') or s.get('status') == 'done':
            return ''
        s['messages'].append({
            'type': 'ask',
            'id': ask_id,
            'text': question,
        })
        s['pending_ask'] = {
            'id': ask_id,
            'event': event,
            'result': result_box,
        }

    event.wait(timeout=timeout)

    with _lock:
        s = _sessions.get(sid)
        if s and (s.get('pending_ask') or {}).get('id') == ask_id:
            s['pending_ask'] = None

    return result_box[0] or ''


def ask_user(question: str) -> str:
    """Show a question as an AI chat bubble and block until the user replies.

    The question appears in the 小艺 panel as an AI bubble.  The frontend
    detects the pending ask and routes the next user input back here instead
    of starting a new AIOS task.  Times out after 5 minutes.

    Args:
        question: The question to show the user.

    Returns:
        The user's free-text reply, or an empty string on timeout.
    """
    sid = _session_id_var.get()
    if not sid:
        # No active session — fall back to console
        print(f"\nQuestion: {question}")
        try:
            return input("Your reply: ")
        except (EOFError, UnicodeDecodeError):
            return ''

    return ask_user_for_session(sid, question)


def respond_ask(session_id: str, reply: str) -> bool:
    """Called by the server /api/assistant/reply when the user submits a reply."""
    with _lock:
        s = _sessions.get(session_id)
        if not s:
            return False
        pending = s.get('pending_ask')
        if not pending:
            return False
        pending['result'][0] = reply
        pending['event'].set()
    return True


# ---------------------------------------------------------------------------
# Server polling helpers
# ---------------------------------------------------------------------------

def poll_messages(session_id: str, cursor: int = 0) -> dict:
    """Return messages since cursor index, and current status."""
    with _lock:
        s = _sessions.get(session_id)
        if not s:
            return {'found': False}
        new_msgs = s['messages'][cursor:]
        return {
            'found': True,
            'status': s['status'],
            'messages': new_msgs,
            'cursor': cursor + len(new_msgs),
        }


def push_incoming_display(session_id: str, sender: str, content: str) -> None:
    """Push the incoming message label + bubble directly into session['messages'].

    Uses the session_id directly, bypassing ContextVar, so it works reliably
    from any thread (e.g., the Flask request handler thread).
    """
    if not content:
        return
    with _lock:
        s = _sessions.get(session_id)
        if not s or s.get('cancelled') or s.get('status') == 'done':
            return
        if sender:
            s['messages'].append({'type': 'system', 'text': f'来自 {sender} 的消息'})
        s['messages'].append({'type': 'ai', 'text': content})


def list_sessions() -> list:
    """Return [{id, status}] for all known sessions."""
    with _lock:
        return [
            {'id': sid, 'status': s['status']}
            for sid, s in _sessions.items()
        ]


def cancel_session(session_id: str) -> None:
    """Cancel a running session immediately.

    Marks the session as cancelled so all subsequent push_* calls are no-ops.
    Also unblocks any thread blocked on a pending confirm or ask gate so the
    background worker can exit cleanly rather than hanging forever.
    """
    with _lock:
        s = _sessions.get(session_id)
        if not s:
            return
        s['cancelled'] = True
        s['status'] = 'done'

        # Unblock pending confirm gate.
        pc = s.get('pending_confirm')
        if pc:
            pc['result'][0] = False
            pc['event'].set()
            s['pending_confirm'] = None

        # Unblock pending ask gate.
        pa = s.get('pending_ask')
        if pa:
            pa['result'][0] = '（任务已取消）'
            pa['event'].set()
            s['pending_ask'] = None


def cleanup_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
