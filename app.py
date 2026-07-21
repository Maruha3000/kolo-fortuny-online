import random
import string
import json
import streamlit as st
from supabase import create_client
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone

st.set_page_config(page_title="Koło Fortuny Online", page_icon="🎡", layout="centered")

DEFAULTS = {
    "screen": "home",
    "nickname": "",
    "created_room_code": "",
    "created_room_id": "",
    "is_host": False,
    "guess_letter": "",
}

PHRASES = [
    {"category": "Filmy", "phrase": "KRÓL LEW"},
    {"category": "Filmy", "phrase": "TITANIC"},
    {"category": "Filmy", "phrase": "FORREST GUMP"},
    {"category": "Filmy", "phrase": "INCEPTION"},
    {"category": "Filmy", "phrase": "MATRIX"},
    {"category": "Muzyka", "phrase": "MICHAEL JACKSON"},
    {"category": "Muzyka", "phrase": "QUEEN"},
    {"category": "Muzyka", "phrase": "ABBA"},
    {"category": "Muzyka", "phrase": "BEATLES"},
    {"category": "Muzyka", "phrase": "FREDERIC CHOPIN"},
    {"category": "Powiedzenia", "phrase": "LEPSZY WRÓBEL W GARŚCI"},
    {"category": "Powiedzenia", "phrase": "GDZIE KUCHAREK SZEŚĆ TAM NIE MA CO JEŚĆ"},
    {"category": "Powiedzenia", "phrase": "NIE MA DYMU BEZ OGNIA"},
    {"category": "Powiedzenia", "phrase": "CO ZA DUŻO TO NIE ZDROWO"},
    {"category": "Powiedzenia", "phrase": "BEZ PRACY NIE MA KOŁACZY"},
    {"category": "Sport", "phrase": "ROBERT LEWANDOWSKI"},
    {"category": "Sport", "phrase": "LEO MESSI"},
    {"category": "Sport", "phrase": "RAFAEL NADAL"},
    {"category": "Sport", "phrase": "USAIN BOLT"},
    {"category": "Sport", "phrase": "MICHAEL JORDAN"},
    {"category": "Podróże", "phrase": "WAKACJE NAD MORZEM"},
    {"category": "Podróże", "phrase": "WIZYTA W PARYŻU"},
    {"category": "Podróże", "phrase": "WYCIECZKA W GÓRY"},
    {"category": "Podróże", "phrase": "SAFARI W AFRYCE"},
    {"category": "Podróże", "phrase": "REJS DOOKOŁA ŚWIATA"},
    {"category": "Jedzenie", "phrase": "PIZZA Z SEREM"},
    {"category": "Jedzenie", "phrase": "SCHABOWY Z ZIEMNIAKAMI"},
    {"category": "Jedzenie", "phrase": "ROSÓŁ Z MAKARONEM"},
    {"category": "Jedzenie", "phrase": "PIEROGI RUSKIE"},
    {"category": "Jedzenie", "phrase": "BIGOS Z KAPUSTY"},
    {"category": "Technologia", "phrase": "SZTUCZNA INTELIGENCJA"},
    {"category": "Technologia", "phrase": "INTERNET RZECZY"},
    {"category": "Technologia", "phrase": "WIRTUALNA RZECZYWISTOŚĆ"},
    {"category": "Technologia", "phrase": "BLOCKCHAIN"},
    {"category": "Technologia", "phrase": "KOMPUTER KWANTOWY"},
]

WHEEL_VALUES = [100, 150, 200, 250, 300, 400, 500, 700]
SPIN_DURATION_SECONDS = 3
TOTAL_ROUNDS = 3

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def generate_room_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def open_room(room_id, room_code, nickname, is_host):
    st.session_state.created_room_id = room_id
    st.session_state.created_room_code = room_code
    st.session_state.nickname = nickname
    st.session_state.is_host = is_host
    st.session_state.screen = "lobby"
    st.rerun()


def normalize_phrase(text):
    return text.strip().upper()


def mask_phrase(phrase, guessed_letters):
    # Ujednolicenie zapisu liter z Supabase (także polskich znaków).
    guessed_set = {str(letter).strip().upper() for letter in (guessed_letters or [])}
    visible = []
    for char in str(phrase or ""):
        if char == " ":
            visible.append("  ")
        elif char.upper() in guessed_set:
            visible.append(char)
        else:
            visible.append("_")
    return " ".join(visible)


def safe_list(value):
    """Bezpiecznie konwertuje cokolwiek z bazy na listę stringów."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).upper().strip() for x in value if x is not None]
    if isinstance(value, str):
        text = value.strip()
        if not text or text in ("{}", "[]", ""):
            return []
        # Postgres zwraca czasem {A,B,C}
        if text.startswith("{") and text.endswith("}"):
            text = text[1:-1]
        # JSON: ["A","B"]
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x).upper().strip() for x in parsed if x is not None]
            except Exception:
                pass
        # Po przecinku: A,B,C
        return [item.strip().upper() for item in text.split(",") if item.strip()]
    return []


def text_to_list(text_value):
    if text_value is None:
        return []
    if isinstance(text_value, list):
        return text_value
    if isinstance(text_value, str):
        if text_value.strip() == "":
            return []
        return [item.strip() for item in text_value.split(",") if item.strip()]
    return []


def list_to_text(list_value):
    if list_value is None:
        return ""
    if isinstance(list_value, list):
        return ",".join(str(item) for item in list_value)
    return str(list_value)


def get_room_and_players(supabase, room_id):
    room_response = (
        supabase.table("game_rooms")
        .select("*")
        .eq("id", room_id)
        .limit(1)
        .execute()
    )
    players_response = (
        supabase.table("game_players")
        .select("id, nickname, is_host, total_score, round_scores")
        .eq("room_id", room_id)
        .order("is_host", desc=True)
        .execute()
    )
    room = room_response.data[0] if room_response.data else None
    players = players_response.data if players_response.data else []
    return room, players


def get_current_player(players, turn_index):
    if not players:
        return None
    return players[turn_index % len(players)]


def start_game_for_room(supabase, room_id):
    selected = random.choice(PHRASES)
    phrase = normalize_phrase(selected["phrase"])
    update_data = {
        "status": "playing",
        "current_phrase": phrase,
        "current_category": selected["category"],
        "guessed_letters": [],
        "current_turn_index": 0,
        "current_spin_value": 0,
        "spin_status": "idle",
        "last_spin_value": 0,
        "last_spin_player": None,
        "spin_timestamp": None,
    }
    supabase.table("game_rooms").update(update_data).eq("id", room_id).execute()
    players = supabase.table("game_players").select("id").eq("room_id", room_id).execute()
    for p in players.data:
        supabase.table("game_players").update({"total_score": 0}).eq("id", p["id"]).execute()


def next_turn(supabase, room_id, current_turn_index):
    supabase.table("game_rooms").update({
        "current_turn_index": current_turn_index + 1,
        "current_spin_value": 0,
        "spin_status": "idle",
        "spin_timestamp": None,
    }).eq("id", room_id).execute()


def spin_wheel(supabase, room_id, player_nickname):
    spin_value = random.choice(WHEEL_VALUES)
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("game_rooms").update({
        "current_spin_value": spin_value,
        "spin_status": "spinning",
        "last_spin_value": spin_value,
        "last_spin_player": player_nickname,
        "spin_timestamp": now_iso,
    }).eq("id", room_id).execute()
    return spin_value


def is_spin_finished(room):
    spin_ts = room.get("spin_timestamp")
    if not spin_ts:
        return False
    try:
        ts = datetime.fromisoformat(str(spin_ts).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed = (now - ts).total_seconds()
        return elapsed >= SPIN_DURATION_SECONDS
    except Exception:
        return False


# ========== DŹWIĘKI JS ==========

def get_sounds_js():
    return """
    <script>
    window.kfAudio = window.kfAudio || { ctx: null, enabled: false, last: "" };

    window.enableKfAudio = function() {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return false;
        if (!window.kfAudio.ctx) window.kfAudio.ctx = new AudioCtx();
        if (window.kfAudio.ctx.state === "suspended") window.kfAudio.ctx.resume();
        window.kfAudio.enabled = true;
        return true;
      } catch (e) { return false; }
    };

    window.playKfSound = function(kind) {
      if (!window.enableKfAudio()) return;
      const ctx = window.kfAudio.ctx;
      const beep = (frequency, duration, type, volume, delay) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = type || "sine";
        osc.frequency.setValueAtTime(frequency, ctx.currentTime + delay);
        gain.gain.setValueAtTime(volume || 0.08, ctx.currentTime + delay);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + duration);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(ctx.currentTime + delay); osc.stop(ctx.currentTime + delay + duration);
      };
      if (kind === "spin") { beep(180, .12, "sawtooth", .07, 0); beep(260, .18, "sawtooth", .07, .12); }
      else if (kind === "tick") beep(850, .035, "square", .035, 0);
      else if (kind === "win") [523,659,784,1047].forEach((f,i)=>beep(f,.22,"sine",.09,i*.11));
      else if (kind === "hit") { beep(880,.12,"sine",.09,0); beep(1320,.18,"sine",.08,.10); }
      else if (kind === "miss") beep(155,.28,"sawtooth",.07,0);
      else if (kind === "phrasewin") [392,523,659,784,1047,1319].forEach((f,i)=>beep(f,.18,"sine",.08,i*.09));
      else if (kind === "newround") { beep(659,.16,"triangle",.08,0); beep(880,.25,"triangle",.08,.15); }
    };

    document.addEventListener("pointerdown", () => window.enableKfAudio(), { once: true });
    document.addEventListener("keydown", () => window.enableKfAudio(), { once: true });
    </script>
    """

# ========== KONFETTI ==========

def get_confetti_html():
    return """
    <style>
    .confetti-container {
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        pointer-events: none;
        z-index: 9999;
        overflow: hidden;
    }
    .confetti {
        position: absolute;
        width: 10px; height: 10px;
        animation: confetti-fall 3s ease-out forwards;
    }
    @keyframes confetti-fall {
        0% { transform: translateY(-10vh) rotate(0deg); opacity: 1; }
        100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
    }
    </style>
    <script>
    (function() {
        const container = document.createElement('div');
        container.className = 'confetti-container';
        const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFEAA7', '#DDA0DD', '#96CEB4', '#F7DC6F'];
        for (let i = 0; i < 80; i++) {
            const c = document.createElement('div');
            c.className = 'confetti';
            c.style.left = Math.random() * 100 + 'vw';
            c.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            c.style.animationDelay = Math.random() * 2 + 's';
            c.style.animationDuration = (2 + Math.random() * 2) + 's';
            c.style.borderRadius = Math.random() > 0.5 ? '50%' : '0';
            container.appendChild(c);
        }
        document.body.appendChild(container);
        setTimeout(() => container.remove(), 5000);
    })();
    </script>
    """


# ========== KOŁO ==========

def render_wheel(spin_status, spin_value, player_name, is_my_turn, spin_timestamp):
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F"]
    segments = len(WHEEL_VALUES)
    angle_per_segment = 360 / segments

    gradient_stops = []
    for i, val in enumerate(WHEEL_VALUES):
        start = i * angle_per_segment
        end = (i + 1) * angle_per_segment
        gradient_stops.append(f"{colors[i % len(colors)]} {start}deg {end}deg")
    conic_gradient = "conic-gradient(" + ", ".join(gradient_stops) + ")"

    try:
        target_idx = WHEEL_VALUES.index(spin_value)
    except ValueError:
        target_idx = 0

    target_center_angle = target_idx * angle_per_segment + angle_per_segment / 2
    final_rotation = (360 - target_center_angle) % 360
    spin_degrees = 5 * 360 + final_rotation

    if spin_status == "spinning":
        anim_class = "wheel-spinning"
        wheel_style = f"transform: rotate({spin_degrees}deg); transition: transform 3s cubic-bezier(0.25, 0.1, 0.25, 1);"
    elif spin_status == "finished":
        anim_class = "wheel-finished"
        wheel_style = f"transform: rotate({spin_degrees}deg); transition: none;"
    else:
        anim_class = "wheel-idle"
        wheel_style = "transform: rotate(0deg); transition: none;"

    html = get_sounds_js() + f"""
    <style>
    .wheel-container {{
        position: relative;
        width: 280px;
        height: 280px;
        margin: 20px auto;
    }}
    .wheel {{
        width: 100%;
        height: 100%;
        border-radius: 50%;
        background: {conic_gradient};
        position: relative;
        box-shadow: 0 0 20px rgba(0,0,0,0.3);
        border: 6px solid #333;
    }}
    .wheel-center {{
        position: absolute;
        top: 50%;
        left: 50%;
        width: 50px;
        height: 50px;
        background: #333;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 12px;
    }}
    .wheel-label {{
        position: absolute;
        top: 50%;
        left: 50%;
        transform-origin: 0 0;
        font-size: 13px;
        font-weight: bold;
        color: #222;
        text-shadow: 0 0 2px white;
        white-space: nowrap;
    }}
    .pointer {{
        position: absolute;
        top: -15px;
        left: 50%;
        transform: translateX(-50%);
        width: 0;
        height: 0;
        border-left: 15px solid transparent;
        border-right: 15px solid transparent;
        border-top: 25px solid #e74c3c;
        z-index: 3;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.4));
    }}
    .spin-overlay {{
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0,0,0,0.75);
        color: white;
        padding: 15px 25px;
        border-radius: 12px;
        font-size: 18px;
        font-weight: bold;
        text-align: center;
        z-index: 4;
        display: none;
        animation: popIn 0.4s ease-out;
    }}
    @keyframes popIn {{
        from {{ transform: translate(-50%, -50%) scale(0.5); opacity: 0; }}
        to   {{ transform: translate(-50%, -50%) scale(1); opacity: 1; }}
    }}
    </style>

    <div style="text-align:center; margin-top:8px;">
        <button onclick="window.enableKfAudio(); window.playKfSound('hit'); this.textContent='🔊 Dźwięk włączony'" style="padding:8px 14px; border-radius:8px; border:1px solid #555; background:#1f6feb; color:white; cursor:pointer; font-weight:bold;">🔇 Kliknij, aby włączyć dźwięk</button>
    </div>
    <div class="wheel-container">
        <div class="pointer"></div>
        <div class="wheel {anim_class}" id="fortuneWheel" style="{wheel_style}">
            <div class="wheel-center">🎡</div>
    """

    for i, val in enumerate(WHEEL_VALUES):
        mid_angle = i * angle_per_segment + angle_per_segment / 2
        label_style = f"transform: translate(-50%, -50%) rotate({mid_angle}deg) translateY(-75px);"
        html += f'            <div class="wheel-label" style="{label_style}">{val}</div>\n'

    html += f"""
        </div>
        <div class="spin-overlay" id="spinOverlay">
            <div>🎯 {spin_value} pkt</div>
            <div style="font-size:13px; margin-top:4px; opacity:0.85;">{player_name or ""}</div>
        </div>
    </div>

    <script>
    (function() {{
        const overlay = document.getElementById('spinOverlay');
        const status = "{spin_status}";
        const spinTs = "{spin_timestamp or ''}";

        if (status === "spinning") {{
            overlay.style.display = "none";
            let elapsed = 0;
            if (spinTs) {{
                elapsed = (Date.now() - new Date(spinTs).getTime()) / 1000;
            }}
            let remaining = Math.max(0, 3100 - elapsed * 1000);

            let tickCount = 0;
            const tickInterval = setInterval(() => {{
                if (window.playSound && tickCount < 8) {{
                    window.playKfSound('tick');
                    tickCount++;
                }}
            }}, 350);

            setTimeout(() => {{
                clearInterval(tickInterval);
                overlay.style.display = "block";
                overlay.innerHTML = '<div>🎯 {spin_value} pkt</div><div style="font-size:13px;margin-top:4px;opacity:0.85;">{player_name or ""}</div>';
                if (window.playSound) window.playKfSound('win');
            }}, remaining);
        }} else if (status === "finished") {{
            overlay.style.display = "block";
            overlay.innerHTML = '<div>🎯 {spin_value} pkt</div><div style="font-size:13px;margin-top:4px;opacity:0.85;">{player_name or ""}</div>';
        }} else {{
            overlay.style.display = "none";
        }}
    }})();
    </script>
    <script>
    document.addEventListener('click', function() {{
        if (window.initAudio) window.enableKfAudio();
    }}, {{once: true}});
    </script>
    """
    return html


# ========== UI ==========

st.title("🎡 Koło Fortuny Online")
st.caption("Graj online ze znajomymi w jednym pokoju.")

st.components.v1.html(get_sounds_js(), height=0)

if "audio_enabled" not in st.session_state:
    st.session_state.audio_enabled = False


if st.session_state.screen == "home":
    nickname = st.text_input(
        "Twój nick",
        value=st.session_state.nickname,
        placeholder="Wpisz nick, np. Artur"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Utwórz pokój", use_container_width=True):
            clean_nick = nickname.strip()
            if len(clean_nick) < 2:
                st.error("Nick musi mieć co najmniej 2 znaki.")
            else:
                try:
                    supabase = get_supabase()
                    room_code = generate_room_code()
                    room_response = (
                        supabase.table("game_rooms")
                        .insert({
                            "room_code": room_code,
                            "status": "waiting",
                            "category_mode": "all",
                            "selected_categories": [],
                            "current_phrase": None,
                            "current_category": None,
                            "guessed_letters": [],
                            "current_turn_index": 0,
                            "current_spin_value": 0,
                            "spin_status": "idle",
                            "last_spin_value": 0,
                            "last_spin_player": None,
                            "spin_timestamp": None,
                        })
                        .select("id, room_code")
                        .execute()
                    )
                    room = room_response.data[0]
                    supabase.table("game_players").insert({
                        "room_id": room["id"],
                        "nickname": clean_nick,
                        "is_host": True,
                        "total_score": 0,
                    }).execute()
                    open_room(room["id"], room["room_code"], clean_nick, True)
                except Exception as e:
                    st.error(f"Nie udało się utworzyć pokoju: {e}")
    with col2:
        if st.button("Dołącz do pokoju", use_container_width=True):
            clean_nick = nickname.strip()
            if len(clean_nick) < 2:
                st.error("Nick musi mieć co najmniej 2 znaki.")
            else:
                st.session_state.nickname = clean_nick
                st.session_state.screen = "join_room"
                st.rerun()


if st.session_state.screen == "join_room":
    st.subheader("Dołączanie do pokoju")
    room_code_input = st.text_input("Kod pokoju", placeholder="Np. ABC123")
    col_back, col_join = st.columns(2)
    with col_back:
        if st.button("Wróć", use_container_width=True):
            st.session_state.screen = "home"
            st.rerun()
    with col_join:
        if st.button("Dołącz", type="primary", use_container_width=True):
            clean_nick = st.session_state.nickname.strip()
            room_code_clean = room_code_input.strip().upper()
            if not room_code_clean:
                st.error("Podaj kod pokoju.")
            else:
                try:
                    supabase = get_supabase()
                    room_response = (
                        supabase.table("game_rooms")
                        .select("id, room_code, status")
                        .eq("room_code", room_code_clean)
                        .limit(1)
                        .execute()
                    )
                    if not room_response.data:
                        st.error("Nie znaleziono pokoju o takim kodzie.")
                    else:
                        room = room_response.data[0]
                        if room["status"] != "waiting":
                            st.error("Ta gra już się rozpoczęła.")
                        else:
                            existing_player = (
                                supabase.table("game_players")
                                .select("id")
                                .eq("room_id", room["id"])
                                .eq("nickname", clean_nick)
                                .limit(1)
                                .execute()
                            )
                            if not existing_player.data:
                                supabase.table("game_players").insert({
                                    "room_id": room["id"],
                                    "nickname": clean_nick,
                                    "is_host": False,
                                    "total_score": 0,
                                }).execute()
                            open_room(room["id"], room["room_code"], clean_nick, False)
                except Exception as e:
                    st.error(f"Nie udało się dołączyć do pokoju: {e}")


# ========== GRA ==========

if st.session_state.screen in ["lobby", "game"]:
    st_autorefresh(interval=2000, key="auto_refresh", debounce=True)

    try:
        supabase = get_supabase()
        room, players = get_room_and_players(supabase, st.session_state.created_room_id)

        if not room:
            st.error("Nie znaleziono pokoju.")
        else:
            if room["status"] == "waiting":
                if not st.session_state.audio_enabled:
                    if st.button("🔊 Włącz dźwięki", use_container_width=True):
                        st.session_state.audio_enabled = True
                        st.components.v1.html("<script>window.enableKfAudio();</script>", height=0)
                        st.success("Dźwięki włączone! 🎵")
                        st.rerun()
                else:
                    st.write("🔊 Dźwięki włączone")

                st.subheader("Poczekalnia")
                st.success(f"Jesteś w pokoju: {st.session_state.created_room_code}")
                st.write(f"**Twój nick:** {st.session_state.nickname}")
                st.write("### Gracze w pokoju")
                for player in players:
                    host_label = " — host" if player["is_host"] else ""
                    st.write(f"• {player['nickname']}{host_label}")

                col_refresh, col_action = st.columns(2)
                with col_refresh:
                    if st.button("Odśwież listę", use_container_width=True):
                        st.rerun()
                with col_action:
                    if st.session_state.is_host:
                        if st.button("Rozpocznij grę", type="primary", use_container_width=True):
                            start_game_for_room(supabase, st.session_state.created_room_id)
                            st.session_state.screen = "game"
                            st.rerun()
                    else:
                        st.info("Czekasz, aż host rozpocznie grę.")

            else:
                st.session_state.screen = "game"

                phrase = room.get("current_phrase") or ""
                category = room.get("current_category") or "Bez kategorii"
                guessed_letters = safe_list(room.get("guessed_letters"))
                current_turn_index = room.get("current_turn_index") or 0
                current_spin_value = room.get("current_spin_value") or 0
                spin_status = room.get("spin_status") or "idle"
                last_spin_value = room.get("last_spin_value") or 0
                last_spin_player = room.get("last_spin_player") or ""
                spin_timestamp = room.get("spin_timestamp")

                if "current_round" not in st.session_state:
                    st.session_state.current_round = 1
                if "used_phrases" not in st.session_state:
                    st.session_state.used_phrases = [phrase]
                if "game_phase" not in st.session_state:
                    st.session_state.game_phase = "playing"

                current_round = st.session_state.current_round
                game_phase = st.session_state.game_phase
                used_phrases = st.session_state.used_phrases

                spin_finished = is_spin_finished(room)

                masked = mask_phrase(phrase, guessed_letters)
                current_player = get_current_player(players, current_turn_index)
                my_player = next(
                    (p for p in players if p["nickname"] == st.session_state.nickname), None
                )
                my_turn = current_player and my_player and current_player["id"] == my_player["id"]

                # ========== PODSUMOWANIE RUNDY ==========
                if game_phase == "round_summary":
                    st.subheader(f"📊 Podsumowanie rundy {current_round}")
                    st.balloons()
                    sorted_players = sorted(players, key=lambda p: p.get("total_score", 0), reverse=True)
                    st.write("### Wyniki po tej rundzie:")
                    for i, player in enumerate(sorted_players, 1):
                        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                        st.write(f"{medal} **{player['nickname']}**: {player['total_score']} pkt")
                    st.write(f"### Hasło w tej rundzie: `{phrase}`")
                    st.write(f"**Kategoria:** {category}")

                    if st.session_state.is_host:
                        if current_round >= TOTAL_ROUNDS:
                            if st.button("🏆 Zakończ grę i pokaż wyniki", type="primary", use_container_width=True):
                                st.session_state.game_phase = "game_over"
                                st.rerun()
                        else:
                            if st.button("➡️ Następna runda", type="primary", use_container_width=True):
                                available = [p for p in PHRASES if normalize_phrase(p["phrase"]) not in used_phrases]
                                if not available:
                                    available = PHRASES
                                selected = random.choice(available)
                                new_phrase = normalize_phrase(selected["phrase"])
                                supabase.table("game_rooms").update({
                                    "current_phrase": new_phrase,
                                    "current_category": selected["category"],
                                    "guessed_letters": [],
                                    "current_turn_index": 0,
                                    "current_spin_value": 0,
                                    "spin_status": "idle",
                                    "last_spin_value": 0,
                                    "last_spin_player": None,
                                    "spin_timestamp": None,
                                }).eq("id", st.session_state.created_room_id).execute()
                                st.session_state.current_round = current_round + 1
                                st.session_state.used_phrases = used_phrases + [new_phrase]
                                st.session_state.game_phase = "playing"
                                st.rerun()
                    else:
                        if current_round >= TOTAL_ROUNDS:
                            st.info("Czekasz na zakończenie gry przez hosta...")
                        else:
                            st.info("Czekasz, aż host rozpocznie następną rundę...")

                    if st.button("Wróć do strony głównej"):
                        st.session_state.screen = "home"
                        st.rerun()
                    st.stop()

                # ========== KONIEC GRY ==========
                if game_phase == "game_over":
                    st.components.v1.html(get_confetti_html(), height=0)
                    st.subheader("🏆 KONIEC GRY 🏆")
                    sorted_players = sorted(players, key=lambda p: p.get("total_score", 0), reverse=True)
                    st.components.v1.html("<script>if(window.playSound) window.playKfSound('game_over');</script>", height=0)
                    st.write("## 🎉 Podium 🎉")
                    cols = st.columns(min(3, len(sorted_players)))
                    podium_colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
                    podium_emojis = ["🥇", "🥈", "🥉"]
                    for i, (col, player) in enumerate(zip(cols, sorted_players)):
                        with col:
                            st.markdown(f"""
                            <div style="text-align:center; padding:20px; background:{podium_colors[i]};
                            border-radius:15px; margin:10px 0; box-shadow:0 4px 15px rgba(0,0,0,0.2);">
                                <div style="font-size:40px;">{podium_emojis[i]}</div>
                                <div style="font-size:20px; font-weight:bold; color:#333;">{player['nickname']}</div>
                                <div style="font-size:24px; color:#333;">{player['total_score']} pkt</div>
                            </div>
                            """, unsafe_allow_html=True)
                    if len(sorted_players) > 3:
                        st.write("### Pozostali gracze:")
                        for i, player in enumerate(sorted_players[3:], 4):
                            st.write(f"{i}. {player['nickname']}: {player['total_score']} pkt")
                    if st.button("🔄 Nowa gra", use_container_width=True):
                        for key in ["current_round", "used_phrases", "game_phase"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.session_state.screen = "home"
                        st.rerun()
                    st.stop()

                # ========== NORMALNA GRA ==========
                st.subheader(f"🎡 Runda {current_round} / {TOTAL_ROUNDS}")
                st.write(f"**Kod pokoju:** {st.session_state.created_room_code}")
                st.write(f"**Kategoria:** {category}")
                st.write(f"**Hasło:** `{masked}`")

                if current_player:
                    st.info(f"Tura gracza: {current_player['nickname']}")

                wheel_html = render_wheel(
                    spin_status=spin_status,
                    spin_value=last_spin_value,
                    player_name=last_spin_player,
                    is_my_turn=my_turn,
                    spin_timestamp=spin_timestamp,
                )
                st.components.v1.html(wheel_html, height=390)

                if spin_status == "spinning":
                    if spin_finished:
                        st.success(f"🎯 Koło zatrzymało się na: **{last_spin_value} pkt** (kręcił: {last_spin_player})")
                    else:
                        st.write(f"🔄 **{last_spin_player}** kręci kołem...")
                elif spin_status == "finished":
                    st.success(f"🎯 Koło zatrzymało się na: **{last_spin_value} pkt** (kręcił: {last_spin_player})")

                st.write("### Wyniki")
                for player in players:
                    marker = " ← teraz gra" if current_player and player["id"] == current_player["id"] else ""
                    st.write(f"• {player['nickname']}: {player['total_score']} pkt{marker}")

                phrase_guessed = "_" not in masked

                if phrase_guessed:
                    st.success(f"🎉 Hasło zostało odgadnięte: {phrase}")
                    st.components.v1.html("<script>if(window.playSound) window.playKfSound('phrase_win');</script>", height=0)
                    if st.session_state.is_host:
                        if st.button("📊 Pokaż podsumowanie rundy", type="primary", use_container_width=True):
                            st.session_state.game_phase = "round_summary"
                            st.rerun()
                    else:
                        st.info("Czekasz na podsumowanie rundy...")
                    if st.button("Wróć do strony głównej"):
                        st.session_state.screen = "home"
                        st.rerun()
                    st.stop()
                else:
                    col_refresh, col_spin = st.columns(2)
                    with col_refresh:
                        if st.button("Odśwież stan gry", use_container_width=True):
                            st.rerun()
                    with col_spin:
                        if my_turn:
                            if spin_status == "idle":
                                if st.button("Zakręć kołem", type="primary", use_container_width=True):
                                    st.components.v1.html("<script>window.enableKfAudio();</script>", height=0)
                                    spin_wheel(supabase, st.session_state.created_room_id, st.session_state.nickname)
                                    st.rerun()
                            elif spin_status == "spinning":
                                if spin_finished:
                                    if st.button("Zgaduj!", type="primary", use_container_width=True):
                                        supabase.table("game_rooms").update({"spin_status": "finished"}).eq("id", st.session_state.created_room_id).execute()
                                        st.rerun()
                                else:
                                    st.info("Koło się kręci... poczekaj!")
                            else:
                                st.success(f"Koło pokazuje: {current_spin_value} pkt")
                        else:
                            if spin_status == "spinning":
                                st.info(f"{last_spin_player} kręci kołem...")
                            else:
                                st.warning("To nie Twoja tura.")

                    can_guess = my_turn and (spin_status == "finished" or (spin_status == "spinning" and spin_finished))

                    if can_guess:
                        if spin_status == "spinning" and spin_finished:
                            supabase.table("game_rooms").update({"spin_status": "finished"}).eq("id", st.session_state.created_room_id).execute()

                        with st.form("guess_form"):
                            letter_input = st.text_input("Podaj literę", max_chars=1, key="guess_letter")
                            submitted_letter = st.form_submit_button("Zgadnij literę")

                        if submitted_letter:
                            letter = (letter_input or "").strip().upper()
                            if not letter or letter not in string.ascii_uppercase + "ĄĆĘŁŃÓŚŹŻ":
                                st.error("Podaj jedną literę.")
                            elif letter in guessed_letters:
                                st.error("Ta litera była już podana.")
                            else:
                                letter = letter.upper()
                                new_guessed = sorted(set(safe_list(guessed_letters) + [letter]))
                                occurrences = sum(1 for char in phrase.upper() if char == letter)
                                supabase.table("game_rooms").update({
                                    "guessed_letters": new_guessed,
                                    "spin_status": "idle",
                                    "current_spin_value": 0,
                                    "spin_timestamp": None,
                                }).eq("id", st.session_state.created_room_id).execute()

                                if occurrences > 0:
                                    new_score = my_player["total_score"] + (occurrences * current_spin_value)
                                    supabase.table("game_players").update({"total_score": new_score}).eq("id", my_player["id"]).execute()
                                    st.success(f"Trafiona litera: {letter}. Zdobywasz {occurrences * current_spin_value} pkt.")
                                    st.components.v1.html("<script>if(window.playSound) window.playKfSound('hit');</script>", height=0)
                                    st.rerun()
                                else:
                                    next_turn(supabase, st.session_state.created_room_id, current_turn_index)
                                    st.error(f"Brak litery: {letter}. Kolejka przechodzi dalej.")
                                    st.components.v1.html("<script>if(window.playSound) window.playKfSound('miss');</script>", height=0)
                                    st.rerun()

                        with st.form("guess_phrase_form"):
                            full_guess = st.text_input("Zgadnij całe hasło")
                            submitted_phrase = st.form_submit_button("Sprawdź hasło")

                        if submitted_phrase:
                            clean_guess = normalize_phrase(full_guess)
                            if not clean_guess:
                                st.error("Wpisz hasło.")
                            elif clean_guess == phrase:
                                st.success(f"Brawo! Odgadłeś hasło: {phrase}")
                                all_letters = list(set(list(phrase.replace(" ", ""))))
                                supabase.table("game_rooms").update({
                                    "guessed_letters": all_letters,
                                    "spin_status": "idle",
                                    "spin_timestamp": None,
                                }).eq("id", st.session_state.created_room_id).execute()
                                st.rerun()
                            else:
                                st.error("Hasło nieprawidłowe. Tracisz kolejkę.")
                                next_turn(supabase, st.session_state.created_room_id, current_turn_index)
                                st.rerun()

                if st.button("Wróć do strony głównej"):
                    for key in ["current_round", "used_phrases", "game_phase"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.session_state.screen = "home"
                    st.rerun()

    except Exception as e:
        st.error(f"Błąd gry: {e}")
