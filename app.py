import random
import string
import streamlit as st
from supabase import create_client

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
        })
        .eq("id", room_id)
        .execute()
    )


def spin_wheel(supabase, room_id):
    spin_value = random.choice(WHEEL_VALUES)

    (
        supabase.table("game_rooms")
        .update({"current_spin_value": spin_value})
        .eq("id", room_id)
        .execute()
    )

    return spin_value


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


if st.session_state.screen in ["lobby", "game"]:
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
                st.session_state.screen = "game"

                phrase = room.get("current_phrase") or ""
                category = room.get("current_category") or "Bez kategorii"
                guessed_letters = room.get("guessed_letters") or []
                current_turn_index = room.get("current_turn_index") or 0
                current_spin_value = room.get("current_spin_value") or 0

                masked = mask_phrase(phrase, guessed_letters)
                current_player = get_current_player(players, current_turn_index)
                my_player = next(
                    (p for p in players if p["nickname"] == st.session_state.nickname),
                    None
                )

                st.subheader("Gra trwa")
                st.write(f"**Kod pokoju:** {st.session_state.created_room_code}")
                st.write(f"**Kategoria:** {category}")
                st.write(f"**Hasło:** `{masked}`")

                if current_player:
                    st.info(f"Tura gracza: {current_player['nickname']}")

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

                    my_turn = current_player and my_player and current_player["id"] == my_player["id"]

                    with col_spin:
                        if my_turn:
                            if current_spin_value == 0:
                                if st.button("Zakręć kołem", type="primary", use_container_width=True):
                                    value = spin_wheel(supabase, st.session_state.created_room_id)
                                    st.success(f"Wylosowano: {value} pkt")
                                    st.rerun()
                            else:
                                st.success(f"Koło pokazuje: {current_spin_value} pkt")
                        else:
                            st.warning("To nie Twoja tura.")

                    if my_turn and current_spin_value > 0:
                        with st.form("guess_form"):
                            st.text_input("Podaj literę", max_chars=1, key="guess_letter")
                            submitted = st.form_submit_button("Zgadnij literę")

                        if submitted:
                            letter = st.session_state.guess_letter.strip().upper()

                            if not letter or letter not in string.ascii_uppercase + "ĄĆĘŁŃÓŚŹŻ":
                                st.error("Podaj jedną literę.")
                            elif letter in guessed_letters:
                                st.error("Ta litera była już podana.")
                            else:
                                new_guessed = guessed_letters + [letter]
                                occurrences = phrase.count(letter)

                                (
                                    supabase.table("game_rooms")
                                    .update({"guessed_letters": new_guessed})
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

                                    (
                                        supabase.table("game_rooms")
                                        .update({"current_spin_value": 0})
                                        .eq("id", st.session_state.created_room_id)
                                        .execute()
                                    )

                                    st.session_state.guess_letter = ""
                                    st.success(f"Trafiona litera: {letter}. Zdobywasz {occurrences * current_spin_value} pkt.")
                                    st.rerun()
                                else:
                                    st.session_state.guess_letter = ""
                                    next_turn(supabase, st.session_state.created_room_id, current_turn_index)
                                    st.error(f"Brak litery: {letter}. Kolejka przechodzi dalej.")
                                    st.rerun()

                if st.button("Wróć do strony głównej"):
                    st.session_state.screen = "home"
                    st.rerun()

    except Exception as e:
        st.error(f"Błąd gry: {e}")
