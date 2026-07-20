import random
import string
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Koło Fortuny Online", page_icon="🎡", layout="centered")

if "screen" not in st.session_state:
    st.session_state.screen = "home"

if "nickname" not in st.session_state:
    st.session_state.nickname = ""

if "created_room_code" not in st.session_state:
    st.session_state.created_room_code = ""

if "created_room_id" not in st.session_state:
    st.session_state.created_room_id = ""

def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def generate_room_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))

st.title("🎡 Koło Fortuny Online")
st.caption("Graj online ze znajomymi w jednym pokoju.")

if st.session_state.screen == "home":
    st.write("")
    nickname = st.text_input(
        "Twój nick",
        value=st.session_state.nickname,
        placeholder="Wpisz nick, np. Artur"
    )

    st.write("")
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

                    response = (
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

                    created_room = response.data[0]
                    st.session_state.nickname = clean_nick
                    st.session_state.created_room_code = created_room["room_code"]
                    st.session_state.created_room_id = created_room["id"]
                    st.session_state.screen = "room_created"
                    st.rerun()

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

if st.session_state.screen == "room_created":
    st.subheader("Pokój utworzony")
    st.success(f"Twój pokój został utworzony.")
    st.write(f"**Nick hosta:** {st.session_state.nickname}")
    st.write(f"**Kod pokoju:** {st.session_state.created_room_code}")
    st.info("Za chwilę dodamy automatyczne dołączanie hosta do pokoju oraz prawdziwe dołączanie kolejnych graczy.")

    if st.button("Wróć do strony głównej"):
        st.session_state.screen = "home"
        st.rerun()

if st.session_state.screen == "join_room":
    st.divider()
    st.subheader("Dołączanie do pokoju")
    room_code = st.text_input("Kod pokoju", placeholder="Np. ABC123")
    st.info("W następnym kroku podłączymy prawdziwe dołączanie do istniejącego pokoju.")

    if st.button("Wróć"):
        st.session_state.screen = "home"
        st.rerun()
