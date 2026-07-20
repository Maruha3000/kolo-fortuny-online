import streamlit as st

st.set_page_config(page_title="Koło Fortuny Online", page_icon="🎡", layout="centered")

if "screen" not in st.session_state:
    st.session_state.screen = "home"

st.title("🎡 Koło Fortuny Online")
st.caption("Graj online ze znajomymi w jednym pokoju.")

st.write("")
nickname = st.text_input("Twój nick", placeholder="Wpisz nick, np. Artur")

st.write("")
col1, col2 = st.columns(2)

with col1:
    if st.button("Utwórz pokój", use_container_width=True):
        if len(nickname.strip()) < 2:
            st.error("Nick musi mieć co najmniej 2 znaki.")
        else:
            st.session_state.nickname = nickname.strip()
            st.session_state.screen = "create_room"

with col2:
    if st.button("Dołącz do pokoju", use_container_width=True):
        if len(nickname.strip()) < 2:
            st.error("Nick musi mieć co najmniej 2 znaki.")
        else:
            st.session_state.nickname = nickname.strip()
            st.session_state.screen = "join_room"

if st.session_state.screen == "create_room":
    st.divider()
    st.subheader("Tworzenie pokoju")
    st.success(f"Nick zapisany: {st.session_state.nickname}")
    st.info("W następnym kroku podłączymy prawdziwe tworzenie pokoju w Supabase.")

if st.session_state.screen == "join_room":
    st.divider()
    st.subheader("Dołączanie do pokoju")
    st.success(f"Nick zapisany: {st.session_state.nickname}")
    room_code = st.text_input("Kod pokoju", placeholder="Np. ABC123")
    st.info("W następnym kroku podłączymy prawdziwe dołączanie do pokoju w Supabase.")
