"""brother_accounts - several Claude accounts for the FX AI chat, like Dremzo Code's.

Each extra account is a long-lived login token from `claude setup-token` (the same kind of login
the chat already uses). Switching account only changes CLAUDE_CODE_OAUTH_TOKEN for the claude
process - transcripts, skills, CLAUDE.md, settings and MCP all stay in the one ~/.claude, so a
chat keeps its history on any account and `--resume` works across a switch. (Dremzo Code gives
each Claude account its own CLAUDE_CONFIG_DIR instead; that hides ~/.claude's skills and
CLAUDE.md from the second account, which the Houdini chat depends on.)

The built-in account "This computer" is what the chat did before: whatever login the machine
already has (the registry token, or the CLI's own sign-in). It can't be removed.

Tokens are stored encrypted with Windows DPAPI (only this Windows user can decrypt them) in
~/.houdini_brother/accounts.json. Order = priority: the first usable account is used first, and
auto-switch moves a chat to the next one when its account hits a plan limit.
No Qt in here, so it can be tested in plain Python.
"""
import base64, json, os, re, sys, time

HOME = os.path.join(os.path.expanduser("~"), ".houdini_brother")
FILE = os.path.join(HOME, "accounts.json")
BUILTIN = "computer"
AUTO = "auto"            # a chat that follows the priority order instead of one fixed account
# words the CLI and the API use for "out of quota" (same list as Dremzo Code's LIMIT_RE)
LIMIT_RE = re.compile(r"usage limit|rate.?limit|hit your limit|limit reached|quota|resource.?exhausted|"
                      r"too many requests|\b429\b", re.I)
# login variables that must not leak from Houdini's environment into a chosen account
LOGIN_VARS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")


# ---------------------------------------------------------------------------- DPAPI
def _dpapi(data, protect):
    """CryptProtectData / CryptUnprotectData for the current Windows user."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    src, out = BLOB(len(data), buf), BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(src), None if not protect else "fxai", None, None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI %s failed (%d)" % ("encrypt" if protect else "decrypt", ctypes.GetLastError()))
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _seal(token):
    raw = token.encode("utf8")
    return "dpapi:" + base64.b64encode(_dpapi(raw, True) if sys.platform == "win32" else raw).decode("ascii")


def _open(sealed):
    if not sealed or not sealed.startswith("dpapi:"):
        return None
    raw = base64.b64decode(sealed[6:])
    return (_dpapi(raw, False) if sys.platform == "win32" else raw).decode("utf8")


# ---------------------------------------------------------------------------- store
def _read():
    try:
        with open(FILE, encoding="utf8") as fh:
            s = json.load(fh)
        if not isinstance(s, dict):
            raise ValueError
    except (OSError, ValueError):
        s = {}
    accts = [a for a in (s.get("accounts") or []) if isinstance(a, dict) and a.get("id")]
    if not any(a["id"] == BUILTIN for a in accts):
        accts.insert(0, {"id": BUILTIN, "label": "This computer"})
    return {"accounts": accts, "auto_switch": s.get("auto_switch", True), "limited": s.get("limited") or {}}


def _write(s):
    os.makedirs(HOME, exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf8") as fh:
        json.dump(s, fh, indent=1)
    os.replace(tmp, FILE)


def accounts():
    """[{id, label}] in priority order (no tokens)."""
    return [{"id": a["id"], "label": a.get("label") or a["id"]} for a in _read()["accounts"]]


def label(aid):
    for a in accounts():
        if a["id"] == aid:
            return a["label"]
    return "Auto" if aid in (None, AUTO) else aid


def exists(aid):
    return any(a["id"] == aid for a in _read()["accounts"])


def _clean(text):
    return re.sub(r"\s+", "", text or "")


def looks_like_token(text):
    """A setup-token is 'sk-ant-oat01-...'. Accept any sk-ant- token, refuse anything else."""
    return bool(re.match(r"^sk-ant-[A-Za-z0-9_\-]{20,}$", _clean(text)))


def add(name, token):
    token = _clean(token)
    if not looks_like_token(token):
        raise ValueError("That doesn't look like a Claude token (it starts with sk-ant-).")
    s = _read()
    name = (name or "").strip()[:40] or "Account %d" % len(s["accounts"])
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "account"
    aid, n = slug, 2
    while any(a["id"] == aid for a in s["accounts"]) or aid in (BUILTIN, AUTO):
        aid = "%s-%d" % (slug, n); n += 1
    s["accounts"].append({"id": aid, "label": name, "token": _seal(token), "added": int(time.time())})
    _write(s)
    return aid


def rename(aid, name):
    s = _read()
    for a in s["accounts"]:
        if a["id"] == aid and name.strip():
            a["label"] = name.strip()[:40]
    _write(s)


def set_token(aid, token):
    if aid == BUILTIN:
        raise ValueError("This computer's login is the CLI's own - change it with `claude` itself.")
    token = _clean(token)
    if not looks_like_token(token):
        raise ValueError("That doesn't look like a Claude token (it starts with sk-ant-).")
    s = _read()
    for a in s["accounts"]:
        if a["id"] == aid:
            a["token"] = _seal(token)
    s["limited"].pop(aid, None)
    _write(s)


def remove(aid):
    if aid == BUILTIN:
        raise ValueError("This computer's own login can't be removed.")
    s = _read()
    s["accounts"] = [a for a in s["accounts"] if a["id"] != aid]
    s["limited"].pop(aid, None)
    _write(s)


def move(aid, step):
    """Move one account up (-1) or down (+1) the priority order."""
    s = _read()
    ids = [a["id"] for a in s["accounts"]]
    if aid not in ids:
        return
    i = ids.index(aid); j = max(0, min(len(ids) - 1, i + step))
    s["accounts"].insert(j, s["accounts"].pop(i))
    _write(s)


def auto_switch():
    return bool(_read()["auto_switch"])


def set_auto_switch(on):
    s = _read(); s["auto_switch"] = bool(on); _write(s)


# ---------------------------------------------------------------------------- limits
def mark_limited(aid, resets_at=None):
    """Remember that this account is out of quota until resets_at (unix seconds); unknown = 1 hour."""
    s = _read()
    until = float(resets_at) if resets_at else time.time() + 3600
    s["limited"][aid] = until
    _write(s)


def clear_limited(aid):
    s = _read()
    if s["limited"].pop(aid, None) is not None:
        _write(s)


def limited_until(aid):
    until = _read()["limited"].get(aid)
    return until if until and until > time.time() else None


def resolve(choice, exclude=()):
    """The account a chat runs on. choice = an account id, or AUTO/None = the first account in the
    priority order that isn't out of quota. Returns None when every allowed one is limited."""
    ids = [a["id"] for a in _read()["accounts"]]
    if choice not in (None, AUTO) and choice in ids:
        return choice
    pool = [i for i in ids if i not in exclude]
    for i in pool:
        if not limited_until(i):
            return i
    return pool[0] if pool and not exclude else None


def next_account(current, exclude=()):
    """Where auto-switch goes after `current` ran out: the next usable account in priority order."""
    if not auto_switch():
        return None
    ids = [a["id"] for a in _read()["accounts"]]
    for i in ids:
        if i != current and i not in exclude and not limited_until(i):
            return i
    return None


def token_for(aid):
    """The decrypted token for an added account; None for the built-in one."""
    for a in _read()["accounts"]:
        if a["id"] == aid and aid != BUILTIN:
            return _open(a.get("token"))
    return None


def apply_env(env_set, env_remove, aid):
    """Point a process environment at this account. env_set(k, v) / env_remove(k) wrap whatever
    environment object the caller has (QProcessEnvironment, a dict...). The built-in account
    leaves the environment as the chat already built it."""
    if aid in (None, BUILTIN):
        return
    tok = token_for(aid)
    if not tok:
        raise RuntimeError("Account '%s' has no saved token - add it again in Accounts." % label(aid))
    for k in LOGIN_VARS:              # an inherited API key would win over the account's login
        env_remove(k)
    env_set("CLAUDE_CODE_OAUTH_TOKEN", tok)
