import streamlit as st
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wydatki", page_icon="💸", layout="centered")
st.title("💸 Szybki Wydatek")

def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # UWAGA 1: Upewnij się, że nazwa sekretu ("gcp_service_account")
    # pokrywa się z tym, co masz skonfigurowane w st.secrets dla app.py!
    skey = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    client = gspread.authorize(credentials)
    
    # UWAGA 2: Zmień poniższą wartość na dokładną nazwę Twojego pliku w Google Sheets
    sheet = client.open("PIWO")
    
    # Skrypt będzie szukał zakładki o nazwie "Wydatki"
    return sheet.worksheet("WYDATKI")

with st.form("expense_form", clear_on_submit=True):
    st.write("Nowa transakcja")
    
    col1, col2 = st.columns(2)
    with col1:
        kwota = st.number_input("Kwota", min_value=0.0, step=1.0, format="%.2f")
    with col2:
        kategoria = st.selectbox("Kategoria", [
            "NA PÓŹNIEJ", "JEDZENIE", "NAPOJE", "ALKOHOL", "SNUSY", "KOMUNIKACJA"
        ])
    
    notatka = st.text_input("Notatka (opcjonalnie)")
    
    submitted = st.form_submit_button("Zapisz", use_container_width=True)
    
    if submitted:
        if kwota > 0:
            try:
                worksheet = get_google_sheet()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Szybki strzał do API - dopisanie wiersza na dole
                worksheet.append_row([timestamp, kwota, kategoria, notatka])
                st.success(f"Dodano: {kwota} PLN -> {kategoria}")
            except Exception as e:
                st.error(f"Coś gruchnęło: {e}")
                st.info("Sprawdź czy wpisałeś dobrą nazwę pliku w kodzie i czy utworzyłeś zakładkę 'Wydatki'!")
        else:
            st.error("Wprowadź kwotę większą niż 0, byczku.")
