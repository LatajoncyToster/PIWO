import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from zoneinfo import ZoneInfo
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wydatki", layout="centered")

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

st.title("Szybki Wydatek")

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

# --- MODUŁ WPROWADZANIA DANYCH ---
with st.form("expense_form", clear_on_submit=True):
    st.write("Nowa transakcja")
    
    nowa_data = st.date_input("Data transakcji", value=datetime.today())
    
    col1, col2 = st.columns(2)
    with col1:
        kwota = st.number_input("Kwota (PLN)", min_value=0.0, step=1.0, format="%.2f")
    with col2:
        kategoria = st.selectbox("Kategoria", [
            "NA PÓŹNIEJ", "JEDZENIE", "NAPOJE", "ALKOHOL", "SNUSY", 
            "KOMUNIKACJA", "KAUCJA", "ROZRYWKA"
        ])
    
    notatka = st.text_input("Notatka (opcjonalnie)")
    
    submitted = st.form_submit_button("Zapisz", use_container_width=True)
    
    if submitted:
        if kwota > 0:
            try:
                worksheet = get_google_sheet()
                
                obecny_czas = datetime.now(ZoneInfo("Europe/Warsaw")).time()
                timestamp = datetime.combine(nowa_data, obecny_czas).strftime("%Y-%m-%d %H:%M:%S")
                
                worksheet.append_row([timestamp, kwota, kategoria, notatka])
                st.success(f"Dodano: {kwota} PLN -> {kategoria}")
                fetch_data.clear() # Czyszczenie cache po dodaniu
                st.rerun()
            except Exception as e:
                st.error(f"Coś gruchnęło: {e}")
        else:
            st.error("Wprowadź kwotę większą niż 0.")

# --- POBIERANIE I OBRÓBKA DANYCH DO STATYSTYK ---
df = fetch_data()

if not df.empty and 'Kwota' in df.columns:
    # Czyszczenie i konwersja danych
    df['Kwota'] = df['Kwota'].astype(str).str.replace(',', '.').str.replace(' ', '').replace('', '0').astype(float)
    df['Data_Full'] = pd.to_datetime(df['Data'], errors='coerce')
    df['Data_Tylko'] = df['Data_Full'].dt.normalize()
    df = df.dropna(subset=['Data_Full']).copy()

    st.divider()
    st.subheader("Statystyki (Ostatnie 30 dni)")
    
    dzisiaj = pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).normalize().tz_localize(None)
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    dwa_miesiace_temu = dzisiaj - pd.Timedelta(days=60)
    
    df_miesiac = df[df['Data_Tylko'] >= miesiac_temu]
    df_poprzedni = df[(df['Data_Tylko'] >= dwa_miesiace_temu) & (df['Data_Tylko'] < miesiac_temu)]
    
    suma_miesiac = df_miesiac['Kwota'].sum()
    suma_poprzedni = df_poprzedni['Kwota'].sum()
    delta_wydatkow = suma_miesiac - suma_poprzedni
    
    # Delta inverse - wzrost wydatków na czerwono, spadek na zielono
    st.metric(label="Suma wydatków", value=f"{suma_miesiac:.2f} PLN", delta=f"{delta_wydatkow:.2f} PLN względem poprz. 30 dni", delta_color="inverse")
    
    st.write("")
    col_wykres1, col_wykres2 = st.columns([2, 1])
    
    with col_wykres1:
        st.markdown("**Trend dzienny**")
        if not df_miesiac.empty:
            full_range_dni = pd.date_range(start=miesiac_temu, end=dzisiaj, freq='D')
            df_chart_bars = df_miesiac.groupby('Data_Tylko')['Kwota'].sum().reset_index()
            
            empty_days = pd.DataFrame({'Data_Tylko': full_range_dni, 'Kwota': 0})
            df_chart_bars = pd.concat([df_chart_bars, empty_days]).groupby('Data_Tylko')['Kwota'].sum().reset_index()
            
            df_chart_bars['Trend'] = df_chart_bars['Kwota'].ewm(span=5, adjust=False).mean()

            bars = alt.Chart(df_chart_bars).mark_bar(size=12, color='#e74c3c').encode(
                x=alt.X('yearmonthdate(Data_Tylko):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                y=alt.Y('Kwota:Q', title='PLN'),
                tooltip=[alt.Tooltip('Data_Tylko:T', format='%d.%m.%Y', title='Data'), alt.Tooltip('Kwota:Q', title='PLN', format='.2f')]
            )
            
            line = alt.Chart(df_chart_bars).mark_line(color='#3498db', size=3, interpolate='monotone').encode(
                x=alt.X('yearmonthdate(Data_Tylko):O'), 
                y=alt.Y('Trend:Q')
            )
            st.altair_chart(bars + line, use_container_width=True)
        else:
            st.info("Brak wydatków w ostatnich 30 dniach.")
            
    with col_wykres2:
        st.markdown("**Struktura**")
        if not df_miesiac.empty:
            donut = alt.Chart(df_miesiac.groupby('Kategoria')['Kwota'].sum().reset_index()).mark_arc(innerRadius=45).encode(
                theta='Kwota:Q', 
                color=alt.Color('Kategoria:N', legend=alt.Legend(orient="bottom", title=None)), 
                tooltip=['Kategoria', alt.Tooltip('Kwota:Q', format='.2f', title='PLN')]
            ).properties(height=300)
            st.altair_chart(donut, use_container_width=True)
        else:
            st.info("Brak danych.")

    st.markdown("**Ostatnie 5 wpisów**")
    df_disp = df[['Data', 'Kategoria', 'Kwota', 'Notatka']].iloc[::-1].head(5).copy()
    st.dataframe(df_disp.style.format({'Kwota': '{:.2f}'}), hide_index=True, use_container_width=True)

else:
    st.info("Brak danych do wyświetlenia statystyk. Dodaj pierwszy wydatek.")

st.divider()
st.subheader("Szybkie akcje")
col_btn1, col_btn2 = st.columns(2)

# --- MODUŁ COFANIA (USUWANIE REKORDU) ---
with col_btn1:
    if st.button("Cofnij (usuń ostatni)", use_container_width=True):
        try:
            worksheet = get_google_sheet()
            wszystkie_dane = worksheet.get_all_values()
            
            if len(wszystkie_dane) > 1:
                worksheet.delete_rows(len(wszystkie_dane))
                st.success("Ostatni wydatek wyparował z bazy.")
                fetch_data.clear() # Czyścimy cache
                st.rerun() # Przeładowujemy interfejs
            else:
                st.warning("Baza jest pusta (zostały same nagłówki).")
        except Exception as e:
            st.error(f"Błąd przy usuwaniu: {e}")

# --- MODUŁ ODŚWIEŻANIA APLIKACJI ---
with col_btn2:
    if st.button("Odśwież aplikację", use_container_width=True):
        fetch_data.clear()
        st.rerun()
