import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wydatki", page_icon="💸", layout="centered")
st.title("💸 Szybki Wydatek")

# --- FUNKCJA ŁĄCZĄCA Z BAZĄ ---
def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    skey = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    client = gspread.authorize(credentials)
    
    # UWAGA: Podmień ten string na nazwę swojego docelowego skoroszytu na Dysku Google!
    sheet = client.open("PIWO") 
    return sheet.worksheet("WYDATKI")

# --- MODUŁ WPROWADZANIA DANYCH ---
with st.form("expense_form", clear_on_submit=True):
    st.write("Nowa transakcja")
    
    # Kalendarz (domyślnie dzisiaj)
    nowa_data = st.date_input("Data transakcji", value=datetime.today())
    
    col1, col2 = st.columns(2)
    with col1:
        kwota = st.number_input("Kwota (PLN)", min_value=0.0, step=1.0, format="%.2f")
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
                
                # Złączenie wybranej daty (np. z wczoraj) z obecną krakowską godziną
                obecny_czas = datetime.now(ZoneInfo("Europe/Warsaw")).time()
                timestamp = datetime.combine(nowa_data, obecny_czas).strftime("%Y-%m-%d %H:%M:%S")
                
                worksheet.append_row([timestamp, kwota, kategoria, notatka])
                st.success(f"Dodano: {kwota} PLN -> {kategoria}")
            except Exception as e:
                st.error(f"Coś gruchnęło: {e}")
        else:
            st.error("Wprowadź kwotę większą niż 0.")

st.divider()
st.subheader("Szybkie akcje")
col_btn1, col_btn2 = st.columns(2)

# --- MODUŁ COFANIA (USUWANIE REKORDU) ---
with col_btn1:
    if st.button("Cofnij (usuń ostatni)", use_container_width=True):
        try:
            worksheet = get_google_sheet()
            wszystkie_dane = worksheet.get_all_values()
            
            # Zabezpieczenie przed usunięciem wiersza z nagłówkami kolumn
            if len(wszystkie_dane) > 1:
                worksheet.delete_rows(len(wszystkie_dane))
                st.success("Ostatni wydatek wyparował z bazy.")
            else:
                st.warning("Baza jest pusta (zostały same nagłówki).")
        except Exception as e:
            st.error(f"Błąd przy usuwaniu: {e}")

# --- MODUŁ ODŚWIEŻANIA APLIKACJI ---
with col_btn2:
    if st.button("Odśwież aplikację", use_container_width=True):
        st.rerun()
