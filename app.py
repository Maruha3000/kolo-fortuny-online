
import random
import string
import streamlit as st
from supabase import create_client
from streamlit_autorefresh import st_autorefresh

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
    {"category": "Muzyka", "phrase": "MICHAEL JACKSON"},
    {"category": "Powiedzenia", "phrase": "LEPSZY WRÓBEL W GARŚCI"},
    {"category": "Sport", "phrase": "ROBERT LEWANDOWSKI"},
    {"category": "Podróże", "phrase": "WAKACJE NAD MORZEM"},
    {"category": "Jedzenie", "phrase": "PIZZA Z SEREM"},
]

WHEEL_VALUES = [100, 150, 200, 250, 300, 400, 500, 700]

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
    guessed_set = set(guessed_letters or [])
    visible = []

    for char in phrase:
        if char == " ":
            visible.append("  ")
        elif char in guessed_set:
            visible.append(char)
        else:
            visible.append("_")

    return " ".join(visible)


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
        .select("id, nickname, is_host, total_score")
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

    (
        supabase.table("game_rooms")
        .update({
            "status": "playing",
            "current_phrase": phrase,
            "current_category": selected["category"],
            "guessed_letters": [],
            "current_turn_index": 0,
            "current_spin_value": 0,
            "spin_status": "idle",
            "last_spin_value": 0,
            "last_spin_player": None,
        })
        .eq("id", room_id)
        .execute()
    )


def next_turn(supabase, room_id, current_turn_index):
    (
        supabase.table("game_rooms")
        .update({
            "current_turn_index": current_turn_index + 1,
            "current_spin_value": 0,
            "spin_status": "idle",
        })
        .eq("id", room_id)
        .execute()
    )


def spin_wheel(supabase, room_id, player_nickname):
    spin_value = random.choice(WHEEL_VALUES)

    (
        supabase.table("game_rooms")
        .update({
            "current_spin_value": spin_value,
            "spin_status": "spinning",
            "last_spin_value": spin_value,
            "last_spin_player": player_nickname,
        })
        .eq("id", room_id)
        .execute()
    )

    return spin_value


# ========== KOMPONENT HTML+JS: ANIMOWANE KOŁO ==========

def render_wheel(spin_status, spin_value, player_name, is_my_turn):
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F"]
    segments = len(WHEEL_VALUES)
    angle_per_segment = 360 / segments

    # Build conic-gradient string for the wheel
    gradient_stops = []
    for i, val in enumerate(WHEEL_VALUES):
        start = i * angle_per_segment
        end = (i + 1) * angle_per_segment
        gradient_stops.append(f"{colors[i % len(colors)]} {start}deg {end}deg")
    conic_gradient = "conic-gradient(" + ", ".join(gradient_stops) + ")"

    # Find which segment index corresponds to spin_value
    try:
        target_idx = WHEEL_VALUES.index(spin_value)
    except ValueError:
        target_idx = 0

    # The pointer is at top (0 deg). To land on target_idx, we need the center
    # of that segment to point upward. Center of segment = target_idx * angle_per_segment + angle_per_segment/2
    target_center_angle = target_idx * angle_per_segment + angle_per_segment / 2
    # Pointer is fixed at 0 (top), so rotate wheel by (360 - target_center_angle) + full spins
    final_rotation = (360 - target_center_angle) % 360
    # Add 5 full spins for effect
    spin_degrees = 5 * 360 + final_rotation

    # Determine animation class / state
    if spin_status == "spinning":
        anim_class = "wheel-spinning"
        wheel_style = f"transform: rotate({spin_degrees}deg); transition: transform 3s cubic-bezier(0.25, 0.1, 0.25, 1);"
    elif spin_status == "finished":
        anim_class = "wheel-finished"
        wheel_style = f"transform: rotate({spin_degrees}deg); transition: none;"
    else:
        anim_class = "wheel-idle"
        wheel_style = "transform: rotate(0deg); transition: none;"

    html = f"""
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

    <div class="wheel-container">
        <div class="pointer"></div>
        <div class="wheel {anim_class}" id="fortuneWheel" style="{wheel_style}">
            <div class="wheel-center">🎡</div>
    """

    # Place value labels on the wheel
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

        if (status === "spinning") {{
            overlay.style.display = "none";
            setTimeout(() => {{
                overlay.style.display = "block";
                overlay.innerHTML = '<div>🎯 {spin_value} pkt</div><div style="font-size:13px;margin-top:4px;opacity:0.85;">{player_name or ""}</div>';
            }}, 3100);
        }} else if (status === "finished") {{
            overlay.style.display = "block";
            overlay.innerHTML = '<div>🎯 {spin_value} pkt</div><div style="font-size:13px;margin-top:4px;opacity:0.85;">{player_name or ""}</div>';
        }} else {{
            overlay.style.display = "none";
        }}
    }})();
    </script>
    """
    return html


# ========== STRONA GŁÓWNA ==========

st.title("🎡 Koło Fortuny Online")
st.caption("Graj online ze znajomymi w jednym pokoju.")

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
                        })
                        .select("id, room_code")
                        .execute()
                    )
                    room = room_response.data[0]
                    (
                        supabase.table("game_players")
                        .insert({
                            "room_id": room["id"],
                            "nickname": clean_nick,
                            "is_host": True,
                            "total_score": 0
                        })
                        .execute()
                    )
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


# ========== DOŁĄCZANIE DO POKOJU ==========

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
                                (
                                    supabase.table("game_players")
                                    .insert({
                                        "room_id": room["id"],
                                        "nickname": clean_nick,
                                        "is_host": False,
                                        "total_score": 0
                                    })
                                    .execute()
                                )
                            open_room(room["id"], room["room_code"], clean_nick, False)
                except Exception as e:
                    st.error(f"Nie udało się dołączyć do pokoju: {e}")


# ========== POCZEKALNIA / GRA ==========

if st.session_state.screen in ["lobby", "game"]:
    st_autorefresh(interval=2000, key="auto_refresh", debounce=True)

    try:
        supabase = get_supabase()
        room, players = get_room_and_players(supabase, st.session_state.created_room_id)

        if not room:
            st.error("Nie znaleziono pokoju.")
        else:
            if room["status"] == "waiting":
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
                # ========== GRA TRWA ==========
                st.session_state.screen = "game"

                phrase = room.get("current_phrase") or ""
                category = room.get("current_category") or "Bez kategorii"
                guessed_letters = room.get("guessed_letters") or []
                current_turn_index = room.get("current_turn_index") or 0
                current_spin_value = room.get("current_spin_value") or 0
                spin_status = room.get("spin_status") or "idle"
                last_spin_value = room.get("last_spin_value") or 0
                last_spin_player = room.get("last_spin_player") or ""

                masked = mask_phrase(phrase, guessed_letters)
                current_player = get_current_player(players, current_turn_index)
                my_player = next(
                    (p for p in players if p["nickname"] == st.session_state.nickname), None
                )
                my_turn = current_player and my_player and current_player["id"] == my_player["id"]

                st.subheader("Gra trwa")
                st.write(f"**Kod pokoju:** {st.session_state.created_room_code}")
                st.write(f"**Kategoria:** {category}")
                st.write(f"**Hasło:** `{masked}`")

                if current_player:
                    st.info(f"Tura gracza: {current_player['nickname']}")

                # --- ANIMOWANE KOŁO (widoczne dla WSZYSTKICH) ---
                import math
                wheel_html = render_wheel(
                    spin_status=spin_status,
                    spin_value=last_spin_value,
                    player_name=last_spin_player,
                    is_my_turn=my_turn,
                )
                st.components.v1.html(wheel_html, height=340)

                # --- STATUS KOŁA (tekstowy dla pewności) ---
                if spin_status == "spinning":
                    st.write(f"🔄 **{last_spin_player}** kręci kołem...")
                elif spin_status == "finished":
                    st.success(f"🎯 Koło zatrzymało się na: **{last_spin_value} pkt** (kręcił: {last_spin_player})")

                st.write("### Wyniki")
                for player in players:
                    marker = " ← teraz gra" if current_player and player["id"] == current_player["id"] else ""
                    st.write(f"• {player['nickname']}: {player['total_score']} pkt{marker}")

                if "_" not in masked:
                    st.success(f"Hasło zostało odgadnięte: {phrase}")
                else:
                    col_refresh, col_spin = st.columns(2)

                    with col_refresh:
                        if st.button("Odśwież stan gry", use_container_width=True):
                            st.rerun()

                    with col_spin:
                        if my_turn:
                            if spin_status == "idle":
                                if st.button("Zakręć kołem", type="primary", use_container_width=True):
                                    value = spin_wheel(supabase, st.session_state.created_room_id, st.session_state.nickname)
                                    st.rerun()
                            elif spin_status == "spinning":
                                st.info("Koło się kręci... poczekaj!")
                            else:  # finished
                                st.success(f"Koło pokazuje: {current_spin_value} pkt")
                        else:
                            if spin_status == "spinning":
                                st.info(f"{last_spin_player} kręci kołem...")
                            else:
                                st.warning("To nie Twoja tura.")

                    # --- ZGADYWANIE LITERY / HASŁA ---
                    if my_turn and spin_status == "finished":
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
                                new_guessed = guessed_letters + [letter]
                                occurrences = phrase.count(letter)

                                (
                                    supabase.table("game_rooms")
                                    .update({
                                        "guessed_letters": new_guessed,
                                        "spin_status": "idle",
                                        "current_spin_value": 0,
                                    })
                                    .eq("id", st.session_state.created_room_id)
                                    .execute()
                                )

                                if occurrences > 0:
                                    new_score = my_player["total_score"] + (occurrences * current_spin_value)
                                    (
                                        supabase.table("game_players")
                                        .update({"total_score": new_score})
                                        .eq("id", my_player["id"])
                                        .execute()
                                    )
                                    st.success(f"Trafiona litera: {letter}. Zdobywasz {occurrences * current_spin_value} pkt.")
                                    st.rerun()
                                else:
                                    next_turn(supabase, st.session_state.created_room_id, current_turn_index)
                                    st.error(f"Brak litery: {letter}. Kolejka przechodzi dalej.")
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
                                (
                                    supabase.table("game_rooms")
                                    .update({
                                        "guessed_letters": all_letters,
                                        "spin_status": "idle",
                                    })
                                    .eq("id", st.session_state.created_room_id)
                                    .execute()
                                )
                                st.rerun()
                            else:
                                st.error("Hasło nieprawidłowe. Tracisz kolejkę.")
                                next_turn(supabase, st.session_state.created_room_id, current_turn_index)
                                st.rerun()

                if st.button("Wróć do strony głównej"):
                    st.session_state.screen = "home"
                    st.rerun()

    except Exception as e:
        st.error(f"Błąd gry: {e}")
