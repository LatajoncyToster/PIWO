import streamlit as st
import pandas as pd
import gspread
import altair as alt
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
import datetime
from zoneinfo import ZoneInfo

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Alkoholizm", layout="wide")

# --- WSTRZYKNIĘCIE CUSTOM CSS ---
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #1a1c23;
        border: 1px solid #2d303e;
        padding: 5% 5% 5% 10%;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- OPTYMALIZACJA: POŁĄCZENIE I CACHOWANIE DANYCH ---
@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    sheet = client.open('PIWO').sheet1 
    
    @st.cache_data(ttl=600)
    def fetch_data():
        dane_surowe = sheet.get_all_values()
        if len(dane_surowe) > 1:
            return pd.DataFrame(dane_surowe[1:], columns=dane_surowe[0])
        elif len(dane_surowe) == 1:
            return pd.DataFrame(columns=dane_surowe[0])
        else:
            return pd.DataFrame()
    
    # --- MODUŁ WPROWADZANIA DANYCH (SIDEBAR) ---
    with st.sidebar:
        st.header("Dodaj dane")
        with st.form("add_drink_form", clear_on_submit=True):
            nowa_data = st.date_input("Data spożycia", value=datetime.date.today())
            nowy_alko = st.selectbox("Rodzaj trunku", ["Piwo", "Wódka", "Wódka kolorowa", "Wino", "Inne"])
            nowa_ilosc = st.number_input("Ilość [ml]", min_value=0, step=50, value=500)
            nowa_moc = st.number_input("Moc [%]", min_value=0.0, step=0.1, value=5.0)
            # ZMIANA: Uproszczona etykieta zgodnie z wytycznymi
            nowy_opis = st.text_input("Opis", value="")
            
            submit_button = st.form_submit_button("Dodaj trunek")
            
            if submit_button:
                reverse_map = {'Wódka kolorowa': 'vk', 'Piwo': 'p', 'Wódka': 'v', 'Wino': 'w', 'Inne': 'i'}
                skrot_alko = reverse_map[nowy_alko]
                data_str = nowa_data.strftime('%d.%m.%Y')
                strefa_pl = ZoneInfo('Europe/Warsaw')
                nowy_czas = datetime.datetime.now(strefa_pl).strftime('%H:%M') 
                
                try:
                    sheet.append_row([data_str, skrot_alko, float(nowa_ilosc), float(nowa_moc), nowy_czas, nowy_opis], value_input_option='RAW')
                    st.success("Wpis dodany pomyślnie.")
                    fetch_data.clear() 
                    st.rerun() 
                except Exception as e:
                    st.error(f"Błąd zapisu: {e}")
                    
        st.divider()
        st.subheader("Szybkie akcje")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Cofnij"):
                try:
                    wszystkie_dane = sheet.get_all_values()
                    if len(wszystkie_dane) > 1: 
                        sheet.delete_rows(len(wszystkie_dane))
                        fetch_data.clear()
                        st.rerun()
                except Exception as e: st.error(f"Błąd: {e}")
        with col_btn2:
            if st.button("Powtórz"):
                try:
                    wszystkie_dane = sheet.get_all_values()
                    if len(wszystkie_dane) > 1:
                        ostatni = wszystkie_dane[-1]
                        strefa_pl = ZoneInfo('Europe/Warsaw')
                        if len(ostatni) >= 5: ostatni[4] = datetime.datetime.now(strefa_pl).strftime('%H:%M')
                        sheet.append_row(ostatni, value_input_option='RAW')
                        fetch_data.clear()
                        st.rerun()
                except Exception as e: st.error(f"Błąd: {e}")
        
        if st.button("Odśwież dane", use_container_width=True):
            fetch_data.clear()
            st.rerun()

    # --- POBIERANIE I CZYSZCZENIE DANYCH ---
    df = fetch_data()

    if not df.empty:
        df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').str.replace(' ', '').replace('', '0').astype(float)
        df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').str.replace('%', '').str.replace(' ', '').replace('', '0').astype(float)
        df['Czysty etanol [g]'] = (df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789).round(1)
        
        if 'Godz.' not in df.columns: 
            df['Godz.'] = '--:--'
        else: 
            df['Godz.'] = df['Godz.'].fillna('--:--').replace('', '--:--').astype(str)
            
        if 'Opis' not in df.columns:
            df['Opis'] = ''
        else:
            df['Opis'] = df['Opis'].fillna('').astype(str)
        
        mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo', 'v': 'Wódka', 'w': 'Wino', 'i': 'Inne'}
        df['Alkohol'] = df['Alkohol'].replace(mapowanie)
        df['Data'] = pd.to_datetime(df['Data'], format='%d.%m.%Y')
        
        dni_map = {'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa', 'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Saturday': 'Sobota', 'Sunday': 'Niedziela'}
        miesiace_map = {'January': 'Styczeń', 'February': 'Luty', 'March': 'Marzec', 'April': 'Kwiecień', 'May': 'Maj', 'June': 'Czerwiec', 'July': 'Lipiec', 'August': 'Sierpień', 'September': 'Wrzesień', 'October': 'Październik', 'November': 'Listopad', 'December': 'Grudzień'}
        df['Dzień tygodnia'] = df['Data'].dt.day_name().map(dni_map)
        df['Miesiąc'] = df['Data'].dt.month_name().map(miesiace_map)
        kolejnosc_dni = ['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela']
        kolejnosc_miesiecy = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień']

        # --- INTERFEJS GŁÓWNY ---
        st.title("Alkoholizm")
        
        dzisiaj = pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).normalize().tz_localize(None)
        streak = (dzisiaj - df['Data'].max()).days
        if streak < 0: streak = 0 
        
        if streak == 0:
            c_text, c_bg = "#ff4b4b", "rgba(255, 75, 75, 0.15)"
            txt = f"Licznik trzeźwości: {streak} dni"
        elif streak == 1:
            c_text, c_bg = "#ff8c00", "rgba(255, 140, 0, 0.15)"
            txt = f"Licznik trzeźwości: {streak} dzień"
        elif streak == 2:
            c_text, c_bg = "#ffbd45", "rgba(255, 189, 69, 0.15)"
            txt = f"Licznik trzeźwości: {streak} dni"
        else:
            c_text, c_bg = "#21c354", "rgba(33, 195, 84, 0.15)"
            txt = f"Licznik trze
