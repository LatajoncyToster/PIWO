import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials
import re

st.set_page_config(page_title="Finanse", layout="centered")

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
</style>
""", unsafe_allow_html=True)

st.title("Szybki Wpis")

# --- OPTYMALIZACJA: POŁĄCZENIE I CACHOWANIE DANYCH ---
@st.cache_resource
def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    skey = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    client = gspread.authorize(credentials)
    
    sheet = client.open("PIWO") 
    return sheet.worksheet("WYDATKI")

@st.cache_data(ttl=600)
def fetch_data():
    try:
        worksheet = get_google_sheet()
        dane_surowe = worksheet.get_all_values()
        if len(dane_surowe) > 1:
            return pd.DataFrame(dane_surowe[1:], columns=dane_surowe[0])
        elif len(dane_surowe) == 1:
            return pd.DataFrame(columns=dane_surowe[0])
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return pd.DataFrame()

# --- MODUŁ PARSOWANIA KWOTY (KALKULATOR) ---
def parsowanie_kwoty(wyrazenie):
    if not wyrazenie:
        return 0.0
    # Czyszczenie: usuwa "=", spacje i zmienia przecinki na kropki
    czyste = str(wyrazenie).replace(',', '.').replace(' ', '').lstrip('=')
    
    # Zabezpieczenie RegEx: puszcza tylko cyfry, operatory matematyczne i kropki/nawiasy
    if not re.match(r'^[\d\+\-\*\/\.\(\)]+$', czyste):
        return -1.0
        
    try:
        # Ewaluacja równania z palca
        wynik = float(eval(czyste))
        return round(wynik, 2)
    except Exception:
        return -1.0

# --- MODUŁ WPROWADZANIA DANYCH ---
typ_transakcji = st.radio("Rodzaj operacji:", ["Wydatek", "Wpływ"], horizontal=True)

with st.form("expense_form", clear_on_submit=True):
    nowa_data = st.date_input("Data transakcji", value=datetime.today())
    
    col1, col2 = st.columns(2)
    with col1:
        # Zmieniono z number_input na text_input
        kwota_input = st.text_input("Kwota (PLN)", placeholder="np. 9,99+2,30")
    with col2:
        if typ_transakcji == "Wydatek":
            lista_kategorii = ["NA PÓŹNIEJ", "JEDZENIE", "NAPOJE", "ALKOHOL", "SNUSY", "KOMUNIKACJA", "KAUCJA", "ROZRYWKA"]
        else:
            lista_kategorii = ["WYPŁATA", "VINTED / OLX", "ZAROBKI INNE", "ZWROT KAUCJI"]
            
        kategoria = st.selectbox("Kategoria", lista_kategorii)
    
    notatka = st.text_input("Notatka (opcjonalnie)")
    
    submitted = st.form_submit_button("Zapisz w bazie", use_container_width=True)
    
    if submitted:
        # Wywołanie parsera obliczającego równanie
        kwota = parsowanie_kwoty(kwota_input)
        
        if kwota > 0:
            try:
                worksheet = get_google_sheet()
                
                obecny_czas = datetime.now(ZoneInfo("Europe/Warsaw")).time()
                timestamp = datetime.combine(nowa_data, obecny_czas).strftime("%Y-%m-%d %H:%M:%S")
                
                worksheet.append_row([timestamp, kwota, kategoria, notatka, typ_transakcji])
                st.success(f"Dodano {typ_transakcji.lower()}: {kwota} PLN -> {kategoria}")
                fetch_data.clear() 
                st.rerun()
            except Exception as e:
                st.error(f"Coś gruchnęło: {e}")
        else:
            st.error("Błąd. Wpisz poprawną kwotę lub równanie (np. 15.50 + 4,20).")

# --- POBIERANIE I OBRÓBKA DANYCH DO STATYSTYK ---
df = fetch_data()

if not df.empty and 'Kwota' in df.columns:
    df['Kwota'] = df['Kwota'].astype(str).str.replace(',', '.').str.replace(' ', '').replace('', '0').astype(float)
    df['Data_Full'] = pd.to_datetime(df['Data'], errors='coerce')
    df['Data_Tylko'] = df['Data_Full'].dt.normalize()
    df = df.dropna(subset=['Data_Full']).copy()
    
    if 'Typ' not in df.columns:
        df['Typ'] = 'Wydatek'
    else:
        df['Typ'] = df['Typ'].replace('', 'Wydatek').fillna('Wydatek')

    st.divider()
    st.subheader("Statystyki (Ostatnie 30 dni)")
    
    dzisiaj = pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).normalize().tz_localize(None)
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    
    df_miesiac = df[df['Data_Tylko'] >= miesiac_temu].copy()
    
    df_miesiac_wydatki = df_miesiac[df_miesiac['Typ'] == 'Wydatek']
    df_miesiac_wplywy = df_miesiac[df_miesiac['Typ'] == 'Wpływ']
    
    suma_wydatkow = df_miesiac_wydatki['Kwota'].sum()
    suma_wplywow = df_miesiac_wplywy['Kwota'].sum()
    bilans = suma_wplywow - suma_wydatkow
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Bilans Netto", f"{bilans:.2f} PLN")
    m2.metric("Wpływy", f"{suma_wplywow:.2f} PLN")
    m3.metric("Wydatki", f"{suma_wydatkow:.2f} PLN")
    
    st.write("")
    col_wykres1, col_wykres2 = st.columns([2, 1])
    
    with col_wykres1:
        st.markdown("**Cashflow (Wpływy vs Wydatki)**")
        if not df_miesiac.empty:
            full_range_dni = pd.date_range(start=miesiac_temu, end=dzisiaj, freq='D')
            
            df_miesiac['Cashflow'] = df_miesiac.apply(lambda x: x['Kwota'] if x['Typ'] == 'Wpływ' else -x['Kwota'], axis=1)
            df_chart_bars = df_miesiac.groupby('Data_Tylko')['Cashflow'].sum().reset_index()
            
            empty_days = pd.DataFrame({'Data_Tylko': full_range_dni, 'Cashflow': 0})
            df_chart_bars = pd.concat([df_chart_bars, empty_days]).groupby('Data_Tylko')['Cashflow'].sum().reset_index()
            
            kolor_warunek = alt.condition(
                alt.datum.Cashflow > 0,
                alt.value('#2ecc71'),  
                alt.value('#e74c3c')   
            )

            bars = alt.Chart(df_chart_bars).mark_bar(size=12).encode(
                x=alt.X('yearmonthdate(Data_Tylko):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                y=alt.Y('Cashflow:Q', title='PLN'),
                color=kolor_warunek,
                tooltip=[alt.Tooltip('Data_Tylko:T', format='%d.%m.%Y', title='Data'), alt.Tooltip('Cashflow:Q', title='Bilans dnia (PLN)', format='.2f')]
            )
            
            st.altair_chart(bars, use_container_width=True)
        else:
            st.info("Brak transakcji w ostatnich 30 dniach.")
            
    with col_wykres2:
        st.markdown("**Struktura wydatków**")
        if not df_miesiac_wydatki.empty:
            donut = alt.Chart(df_miesiac_wydatki.groupby('Kategoria')['Kwota'].sum().reset_index()).mark_arc(innerRadius=45).encode(
                theta='Kwota:Q', 
                color=alt.Color('Kategoria:N', legend=alt.Legend(orient="bottom", title=None)), 
                tooltip=['Kategoria', alt.Tooltip('Kwota:Q', format='.2f', title='PLN')]
            ).properties(height=300)
            st.altair_chart(donut, use_container_width=True)
        else:
            st.info("Brak wydatków do strukturyzacji.")

    st.markdown("**Ostatnie 5 wpisów**")
    df_disp = df[['Data', 'Typ', 'Kategoria', 'Kwota', 'Notatka']].iloc[::-1].head(5).copy()
    st.dataframe(df_disp.style.format({'Kwota': '{:.2f}'}), hide_index=True, use_container_width=True)

else:
    st.info("Brak danych do wyświetlenia statystyk. Dodaj pierwszą transakcję.")

st.divider()
st.subheader("Szybkie akcje")
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("Cofnij (usuń ostatni wpis)", use_container_width=True):
        try:
            worksheet = get_google_sheet()
            wszystkie_dane = worksheet.get_all_values()
            
            if len(wszystkie_dane) > 1:
                worksheet.delete_rows(len(wszystkie_dane))
                st.success("Ostatni wpis wyparował z bazy.")
                fetch_data.clear() 
                st.rerun() 
            else:
                st.warning("Baza jest pusta (zostały same nagłówki).")
        except Exception as e:
            st.error(f"Błąd przy usuwaniu: {e}")

with col_btn2:
    if st.button("Odśwież aplikację", use_container_width=True):
        fetch_data.clear()
        st.rerun()
