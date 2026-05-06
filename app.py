import streamlit as st
import pandas as pd
import gspread
import altair as alt
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pytz  # Obsługa stref czasowych

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
        return sheet.get_all_records()
    
    # --- MODUŁ WPROWADZANIA DANYCH (SIDEBAR) ---
    with st.sidebar:
        st.header("Dodaj dane")
        with st.form("add_drink_form", clear_on_submit=True):
            nowa_data = st.date_input("Data spożycia", value=datetime.date.today())
            nowy_alko = st.selectbox("Rodzaj trunku", ["Piwo", "Wódka", "Wódka kolorowa", "Wino", "Inne"])
            nowa_ilosc = st.number_input("Ilość [ml]", min_value=0, step=50, value=500)
            nowa_moc = st.number_input("Moc [%]", min_value=0.0, step=0.5, value=5.0)
            
            submit_button = st.form_submit_button("Dodaj trunek")
            
            if submit_button:
                reverse_map = {'Wódka kolorowa': 'vk', 'Piwo': 'p', 'Wódka': 'v', 'Wino': 'w', 'Inne': 'i'}
                skrot_alko = reverse_map[nowy_alko]
                data_str = nowa_data.strftime('%d.%m.%Y')
                
                # ZMIANA: Twarde ustawienie polskiej strefy czasowej
                strefa_pl = pytz.timezone('Europe/Warsaw')
                nowy_czas = datetime.datetime.now(strefa_pl).strftime('%H:%M') 
                
                try:
                    sheet.append_row([data_str, skrot_alko, nowa_ilosc, nowa_moc, nowy_czas])
                    st.success("Wpis dodany pomyślnie.")
                    fetch_data.clear() 
                    st.rerun() 
                except Exception as e:
                    st.error(f"Błąd zapisu do chmury: {e}")
                    
        st.divider()
        st.subheader("Szybkie akcje")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Cofnij"):
                try:
                    wszystkie_dane = sheet.get_all_values()
                    if len(wszystkie_dane) > 1: 
                        sheet.delete_rows(len(wszystkie_dane))
                        st.success("Cofnięto wpis.")
                        fetch_data.clear() 
                        st.rerun()
                    else:
                        st.warning("Brak wpisów.")
                except Exception as e:
                    st.error(f"Błąd: {e}")
                    
        with col_btn2:
            if st.button("Powtórz"):
                try:
                    wszystkie_dane = sheet.get_all_values()
                    if len(wszystkie_dane) > 1:
                        ostatni_rekord = wszystkie_dane[-1]
                        strefa_pl = pytz.timezone('Europe/Warsaw')
                        aktualny_czas = datetime.datetime.now(strefa_pl).strftime('%H:%M')
                        
                        # Aktualizacja czasu powielonego rekordu do obecnego czasu polskiego
                        ostatni_rekord[4] = aktualny_czas if len(ostatni_rekord) > 4 else aktualny_czas
                        
                        sheet.append_row(ostatni_rekord)
                        st.success("Wprowadzono powielony rekord.")
                        fetch_data.clear() 
                        st.rerun()
                    else:
                        st.warning("Baza danych jest pusta.")
                except Exception as e:
                    st.error(f"Błąd: {e}")

    # --- POBIERANIE I CZYSZCZENIE DANYCH (Z CACHE) ---
    data = fetch_data()
    df = pd.DataFrame(data)

    df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').astype(float)
    df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').astype(float)
    df['Czysty etanol [g]'] = (df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789).round(1)
    
    if 'Godz.' not in df.columns:
        df['Godz.'] = '--:--'
    else:
        df['Godz.'] = df['Godz.'].fillna('--:--').astype(str)
        df.loc[df['Godz.'] == '', 'Godz.'] = '--:--'
    
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
    
    ostatni_wpis = df['Data'].max()
    dzisiaj = pd.Timestamp.now(tz=pytz.timezone('Europe/Warsaw')).normalize().tz_localize(None)
    streak = (dzisiaj - ostatni_wpis).days
    if streak < 0: streak = 0 

    if streak == 0:
        st.error(f"Licznik trzeźwości: {streak} dni. Pite dzisiaj.")
    elif streak == 1:
        st.warning(f"Licznik trzeźwości: {streak} dzień. Kac?")
    else:
        st.success(f"Licznik trzeźwości: {streak} dni. Wątroba zgłasza proces regeneracji.")

    col_top1, col_top2 = st.columns(2)

    with col_top1:
        st.subheader("Ostatnie wpisy")
        df_display = df.copy()
        skroty_dni = {'Poniedziałek': 'Pon', 'Wtorek': 'Wto', 'Środa': 'Śro', 'Czwartek': 'Czw', 'Piątek': 'Pią', 'Sobota': 'Sob', 'Niedziela': 'Nie'}
        df_display['Dzień'] = df_display['Dzień tygodnia'].map(skroty_dni)
        df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
        kolumny_widoczne = ['Dzień', 'Data', 'Godz.', 'Alkohol', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']
        df_display = df_display[kolumny_widoczne]
        st.dataframe(df_display.tail(10), hide_index=True, use_container_width=True)

    with col_top2:
        st.subheader("Kalendarz Spożycia (Miesięczny)")
        
        if 'kalendarz_offset' not in st.session_state:
            st.session_state.kalendarz_offset = 0

        col_btn_l, col_miesiac, col_btn_r = st.columns([1, 2, 1])
        
        with col_btn_l:
            if st.button("Poprzedni"):
                st.session_state.kalendarz_offset -= 1
                
        with col_btn_r:
            if st.button("Następny"):
                st.session_state.kalendarz_offset += 1

        aktywna_data = dzisiaj + pd.DateOffset(months=st.session_state.kalendarz_offset)
        
        with col_miesiac:
            st.markdown(f"<h4 style='text-align: center; margin-top: 0px;'>{aktywna_data.strftime('%m.%Y')}</h4>", unsafe_allow_html=True)

        poczatek_miesiaca = aktywna_data.replace(day=1)
        koniec_miesiaca = (poczatek_miesiaca + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
        
        dni_miesiaca = pd.date_range(start=poczatek_miesiaca, end=koniec_miesiaca, freq='D')
        df_kalendarz = pd.DataFrame({'Data': dni_miesiaca})
        
        df_etanol_dziennie = df.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
        df_kalendarz = df_kalendarz.merge(df_etanol_dziennie, on='Data', how='left').fillna(0)
        
        df_kalendarz = df_kalendarz.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        
        nazwy_krotkie = {0: 'Pon', 1: 'Wto', 2: 'Śro', 3: 'Czw', 4: 'Pią', 5: 'Sob', 6: 'Nie'}
        df_kalendarz['Nazwa_dnia'] = df_kalendarz['Data'].dt.dayofweek.map(nazwy_krotkie)
        df_kalendarz['Dzień_miesiąca'] = df_kalendarz['Data'].dt.day.astype(str)
        df_kalendarz['Rząd_tygodnia'] = df_kalendarz['Data'].apply(lambda d: (d.day - 1 + d.replace(day=1).weekday()) // 7)
        
        kolejnosc_kalendarza = ['Pon', 'Wto', 'Śro', 'Czw', 'Pią', 'Sob', 'Nie']
        
        kolorowanie = alt.condition(
            alt.datum['Etanol (g)'] == 0,
            alt.value('#27ae60'),
            alt.Color('Etanol (g):Q', scale=alt.Scale(scheme='reds'), legend=alt.Legend(title="E
