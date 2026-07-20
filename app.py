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
}

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
                            "selected_categories": []
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

                    open_room(
                        room["id"],
                        room["room_code"],
                        clean_nick,
                        True
                    )

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

    room_code_input = st.text_input(
        "Kod pokoju",
        placeholder="Np. ABC123"
    )

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

                            open_room(
                                room["id"],
                                room["room_code"],
                                clean_nick,
                                False
                            )

                except Exception as e:
                    st.error(f"Nie udało się dołączyć do pokoju: {e}")


if st.session_state.screen == "lobby":
    st.subheader("Poczekalnia")
    st.success(f"Jesteś w pokoju: {st.session_state.created_room_code}")
    st.write(f"**Twój nick:** {st.session_state.nickname}")

    try:
        supabase = get_supabase()

        room_response = (
            supabase.table("game_rooms")
            .select("status")
            .eq("id", st.session_state.created_room_id)
            .limit(1)
            .execute()
        )

        players_response = (
            supabase.table("game_players")
            .select("nickname, is_host, total_score")
            .eq("room_id", st.session_state.created_room_id)
            .order("is_host", desc=True)
            .execute()
        )

        room_status = room_response.data[0]["status"]
        players = players_response.data

        st.write("### Gracze w pokoju")

        for player in players:
            host_label = " — host" if player["is_host"] else ""
            st.write(f"• {player['nickname']}{host_label}")

        st.caption(
            f"Liczba graczy: {len(players)}. "
            "Kliknij „Odśwież listę”, aby zobaczyć osoby, które właśnie dołączyły."
        )

        col_refresh, col_action = st.columns(2)

        with col_refresh:
            if st.button("Odśwież listę", use_container_width=True):
                st.rerun()

        with col_action:
            if st.session_state.is_host:
                if room_status == "waiting":
                    if st.button(
                        "Rozpocznij grę",
                        type="primary",
                        use_container_width=True
                    ):
                        (
                            supabase.table("game_rooms")
                            .update({"status": "playing"})
                            .eq("id", st.session_state.created_room_id)
                            .execute()
                        )
                        st.rerun()
                else:
                    st.success("Gra wystartowała — kolejne mechaniki dodamy teraz.")
            else:
                if room_status == "waiting":
                    st.info("Czekasz, aż host rozpocznie grę.")
                else:
                    st.success("Host rozpoczął grę — kolejne mechaniki dodamy teraz.")

        if st.button("Opuść ekran pokoju"):
            st.session_state.screen = "home"
            st.rerun()

    except Exception as e:
        st.error(f"Nie udało się wczytać pokoju: {e}")
