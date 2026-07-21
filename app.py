import os
import time
import random
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Koło Fortuny Online", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Brakuje SUPABASE_URL lub SUPABASE_KEY w secrets / env.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

WHEEL_VALUES = [50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, "BANKRUT", "STOP"]
ALPHABET = list("AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ")


def ensure_player_state(player_row):
    if not player_row:
        return {
            "name": "",
            "score": 0,
            "revealed_letters": [],
        }
    return {
        "name": player_row.get("player_name", ""),
        "score": player_row.get("score", 0) or 0,
        "revealed_letters": player_row.get("revealed_letters", []) or [],
    }


def get_room(code: str):
    res = supabase.table("game_rooms").select("*").eq("room_code", code).limit(1).execute()
    return res.data[0] if res.data else None


def get_players(code: str):
    res = supabase.table("game_players").select("*").eq("room_code", code).order("created_at").execute()
    return res.data or []


def masked_phrase(phrase: str, revealed):
    revealed = set((revealed or []))
    out = []
    for ch in phrase:
        upper = ch.upper()
        if upper == " ":
            out.append("  ")
        elif upper in revealed or upper not in ALPHABET:
            out.append(ch)
        else:
            out.append("_")
    return " ".join(out)


def current_player(players, turn_index):
    if not players:
        return None
    return players[turn_index % len(players)]


def next_turn(room, players):
    if not players:
        return
    turn_index = (room.get("current_turn", 0) or 0) + 1
    supabase.table("game_rooms").update({
        "current_turn": turn_index,
        "spin_status": None,
        "last_spin_player": None,
        "last_spin_value": 0,
    }).eq("id", room["id"]).execute()


def reset_spin_state(room_id):
    supabase.table("game_rooms").update({
        "spin_status": None,
        "last_spin_player": None,
        "last_spin_value": 0,
    }).eq("id", room_id).execute()


def join_room_ui():
    st.title("Koło Fortuny Online")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Dołącz do pokoju")
        room_code = st.text_input("Kod pokoju", key="join_code").strip().upper()
        player_name = st.text_input("Twój nick", key="join_name").strip()
        if st.button("Wejdź do gry", use_container_width=True):
            if not room_code or not player_name:
                st.warning("Podaj kod pokoju i nick.")
                return
            room = get_room(room_code)
            if not room:
                st.error("Nie znaleziono pokoju.")
                return
            token = f"{player_name}-{int(time.time()*1000)}-{random.randint(1000,9999)}"
            existing = supabase.table("game_players").select("id").eq("room_code", room_code).eq("player_name", player_name).limit(1).execute()
            if existing.data:
                st.error("Gracz o takim nicku już jest w pokoju.")
                return
            supabase.table("game_players").insert({
                "room_code": room_code,
                "player_name": player_name,
                "player_token": token,
                "score": 0,
                "revealed_letters": [],
            }).execute()
            st.session_state.room_code = room_code
            st.session_state.player_name = player_name
            st.session_state.player_token = token
            st.rerun()

    with col2:
        st.subheader("Stwórz pokój")
        host_name = st.text_input("Nick hosta", key="host_name").strip()
        phrase = st.text_input("Hasło", key="host_phrase").strip()
        category = st.text_input("Kategoria", key="host_category").strip()
        if st.button("Utwórz pokój", use_container_width=True):
            if not host_name or not phrase:
                st.warning("Podaj nick hosta i hasło.")
                return
            room_code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=6))
            host_token = f"host-{int(time.time()*1000)}-{random.randint(1000,9999)}"
            room_insert = supabase.table("game_rooms").insert({
                "room_code": room_code,
                "host_token": host_token,
                "status": "waiting",
                "category_mode": category or None,
                "selected_categories": [category] if category else [],
                "phrase": phrase,
                "current_turn": 0,
                "spin_status": None,
                "last_spin_player": None,
                "last_spin_value": 0,
            }).execute()
            supabase.table("game_players").insert({
                "room_code": room_code,
                "player_name": host_name,
                "player_token": host_token,
                "score": 0,
                "revealed_letters": [],
            }).execute()
            st.session_state.room_code = room_code
            st.session_state.player_name = host_name
            st.session_state.player_token = host_token
            st.success(f"Pokój utworzony. Kod: {room_code}")
            st.rerun()


def game_ui(room_code, player_name, player_token):
    room = get_room(room_code)
    if not room:
        st.error("Pokój już nie istnieje.")
        if st.button("Wróć"):
            for k in ["room_code", "player_name", "player_token"]:
                st.session_state.pop(k, None)
            st.rerun()
        return

    players = get_players(room_code)
    me = next((p for p in players if p.get("player_token") == player_token), None)
    if not me:
        st.error("Nie znaleziono Cię w pokoju.")
        return

    st.title(f"Koło Fortuny — pokój {room_code}")
    top1, top2, top3 = st.columns([1.5, 1, 1])
    with top1:
        st.write(f"Gracz: **{player_name}**")
    with top2:
        if st.button("Odśwież", use_container_width=True):
            st.rerun()
    with top3:
        auto = st.checkbox("Auto refresh", value=True)

    if auto:
        time.sleep(2)
        st.rerun()

    phrase = room.get("phrase", "")
    all_revealed = set()
    for p in players:
        all_revealed.update((p.get("revealed_letters") or []))

    current = current_player(players, room.get("current_turn", 0) or 0)
    is_my_turn = current and current.get("player_token") == player_token

    info1, info2 = st.columns([2, 1])
    with info1:
        st.subheader("Hasło")
        st.markdown(f"### {masked_phrase(phrase, all_revealed)}")
        if room.get("category_mode"):
            st.caption(f"Kategoria: {room['category_mode']}")
    with info2:
        st.subheader("Tura")
        if current:
            st.info(f"Ruch gracza: {current.get('player_name', '-')}")

    spin_status = room.get("spin_status")
    last_spin_player = room.get("last_spin_player")
    last_spin_value = room.get("last_spin_value")

    if spin_status == "spinning" and last_spin_player:
        st.warning(f"🎡 {last_spin_player} kręci kołem...")
    elif spin_status == "done" and last_spin_player:
        st.success(f"🎯 Koło pokazało: {last_spin_value} pkt — tura gracza {last_spin_player}")

    st.subheader("Wyniki")
    scoreboard = []
    for idx, p in enumerate(players):
        scoreboard.append({
            "Gracz": p.get("player_name"),
            "Punkty": p.get("score", 0) or 0,
            "Na ruchu": "✅" if current and p.get("player_token") == current.get("player_token") else "",
        })
    st.table(scoreboard)

    st.divider()
    if not is_my_turn:
        st.caption("Czekasz na swoją turę.")
        return

    st.subheader("Twoje akcje")

    if "spin_result" not in st.session_state:
        st.session_state.spin_result = None

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Zakręć kołem", use_container_width=True):
            supabase.table("game_rooms").update({
                "spin_status": "spinning",
                "last_spin_player": player_name,
                "last_spin_value": 0,
            }).eq("id", room["id"]).execute()
            time.sleep(1.4)
            result = random.choice(WHEEL_VALUES)
            st.session_state.spin_result = result

            if result == "BANKRUT":
                supabase.table("game_players").update({"score": 0}).eq("id", me["id"]).execute()
                supabase.table("game_rooms").update({
                    "spin_status": "done",
                    "last_spin_player": player_name,
                    "last_spin_value": 0,
                }).eq("id", room["id"]).execute()
                next_turn(room, players)
                st.rerun()

            if result == "STOP":
                supabase.table("game_rooms").update({
                    "spin_status": "done",
                    "last_spin_player": player_name,
                    "last_spin_value": 0,
                }).eq("id", room["id"]).execute()
                next_turn(room, players)
                st.rerun()

            supabase.table("game_rooms").update({
                "spin_status": "done",
                "last_spin_player": player_name,
                "last_spin_value": int(result),
            }).eq("id", room["id"]).execute()
            st.rerun()

    with col_b:
        guess_phrase = st.text_input("Zgadnij całe hasło", key="guess_phrase")
        if st.button("Zgaduję hasło", use_container_width=True):
            if guess_phrase.strip().upper() == phrase.strip().upper():
                letters = sorted({c.upper() for c in phrase if c.upper() in ALPHABET})
                supabase.table("game_players").update({
                    "revealed_letters": letters,
                    "score": (me.get("score", 0) or 0) + 1000,
                }).eq("id", me["id"]).execute()
                supabase.table("game_rooms").update({"status": "finished"}).eq("id", room["id"]).execute()
                st.success("Brawo! Hasło odgadnięte.")
                st.rerun()
            else:
                st.error("To nie to hasło.")
                next_turn(room, players)
                st.rerun()

    spin_result = st.session_state.get("spin_result")
    if isinstance(spin_result, int):
        st.info(f"Wylosowano: {spin_result} pkt. Teraz wybierz literę.")
        chosen_letter = st.selectbox("Litera", [l for l in ALPHABET if l not in all_revealed], key="chosen_letter")
        if st.button("Odkryj literę", use_container_width=True):
            hits = sum(1 for c in phrase.upper() if c == chosen_letter)
            if hits > 0:
                new_letters = sorted(set((me.get("revealed_letters") or []) + [chosen_letter]))
                new_score = (me.get("score", 0) or 0) + hits * spin_result
                supabase.table("game_players").update({
                    "revealed_letters": new_letters,
                    "score": new_score,
                }).eq("id", me["id"]).execute()

                revealed_total = set(all_revealed)
                revealed_total.add(chosen_letter)
                phrase_letters = {c.upper() for c in phrase if c.upper() in ALPHABET}
                if phrase_letters.issubset(revealed_total):
                    supabase.table("game_rooms").update({"status": "finished"}).eq("id", room["id"]).execute()
                reset_spin_state(room["id"])
                st.session_state.spin_result = None
                st.rerun()
            else:
                reset_spin_state(room["id"])
                st.session_state.spin_result = None
                next_turn(room, players)
                st.rerun()
    elif spin_result == "BANKRUT":
        st.error("BANKRUT")
        st.session_state.spin_result = None
    elif spin_result == "STOP":
        st.warning("STOP")
        st.session_state.spin_result = None

    if room.get("status") == "finished":
        winner = max(players, key=lambda p: p.get("score", 0) or 0) if players else None
        st.success(f"Gra zakończona. Wygrał: {winner.get('player_name')}" if winner else "Gra zakończona.")


if "room_code" not in st.session_state or "player_name" not in st.session_state or "player_token" not in st.session_state:
    join_room_ui()
else:
    game_ui(
        st.session_state.room_code,
        st.session_state.player_name,
        st.session_state.player_token,
    )
