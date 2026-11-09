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

# Zmiana tytułu zgodnie z życzeniem
st.title("Wydatki")

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
    czyste = str(wyrazenie).replace(',', '.').replace(' ', '').lstrip('=')
    
    if not re.match(r'^[\d\+\-\*\/\.\(\)]+$', czyste):
        return -1.0
        
    try:
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
        kwota_input = st.text_input("Kwota (PLN)", placeholder="np. 9,99+2,30")
    with col2:
        if typ_transakcji == "Wydatek":
            lista_kategorii = [
                "NA PÓŹNIEJ", "JEDZENIE", "NAPOJE", "ALKOHOL", "SNUSY", 
                "KOMUNIKACJA", "ROZRYWKA", "KOSZTY STAŁE", 
                "XTB", "INNE"
            ]
        else:
            lista_kategorii = [
                "WYPŁATA", "VINTED / OLX", "ZAROBKI INNE", "ZWROT KAUCJI", "INNE"
            ]
            
        kategoria = st.selectbox("Kategoria", lista_kategorii)
    
    notatka = st.text_input("Notatka (opcjonalnie)")
    
    submitted = st.form_submit_button("Zapisz w bazie", use_container_width=True)
    
    if submitted:
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
    st.subheader("Analiza miesięczna")

    # Inicjalizacja offsetu kalendarza w stanie sesji
    if 'miesiac_offset' not in st.session_state: 
        st.session_state.miesiac_offset = 0

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1: 
        if st.button("Poprzedni", use_container_width=True): 
            st.session_state.miesiac_offset -= 1
            st.rerun()
    with c3:
        if st.button("Następny", use_container_width=True): 
            st.session_state.miesiac_offset += 1
            st.rerun()

    # Wyliczanie dat na podstawie offsetu
    dzisiaj = pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).normalize().tz_localize(None)
    pierwszy_dzien_obecnego = dzisiaj.replace(day=1)
    
    aktywny_miesiac_start = pierwszy_dzien_obecnego + pd.DateOffset(months=st.session_state.miesiac_offset)
    aktywny_miesiac_koniec = aktywny_miesiac_start + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    poprzedni_miesiac_start = aktywny_miesiac_start - pd.DateOffset(months=1)

    miesiace_pl = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień']
    nazwa_miesiaca = f"{miesiace_pl[aktywny_miesiac_start.month - 1]} {aktywny_miesiac_start.year}"
    
    with c2: 
        st.markdown(f"<h4 style='text-align: center; margin-top: 0;'>{nazwa_miesiaca}</h4>", unsafe_allow_html=True)
    
    # Filtrowanie Danych po wybranym miesiącu
    df_wybrany = df[(df['Data_Tylko'] >= aktywny_miesiac_start) & (df['Data_Tylko'] <= aktywny_miesiac_koniec)].copy()
    df_poprzedni = df[(df['Data_Tylko'] >= poprzedni_miesiac_start) & (df['Data_Tylko'] < aktywny_miesiac_start)].copy()
    
    df_wybrany_wydatki = df_wybrany[df_wybrany['Typ'] == 'Wydatek']
    df_wybrany_wplywy = df_wybrany[df_wybrany['Typ'] == 'Wpływ']
    
    suma_wydatkow = df_wybrany_wydatki['Kwota'].sum()
    suma_wplywow = df_wybrany_wplywy['Kwota'].sum()
    bilans = suma_wplywow - suma_wydatkow
    
    # Obliczanie delty względem poprzedniego miesiąca
    suma_wydatkow_poprz = df_poprzedni[df_poprzedni['Typ'] == 'Wydatek']['Kwota'].sum()
    suma_wplywow_poprz = df_poprzedni[df_poprzedni['Typ'] == 'Wpływ']['Kwota'].sum()
    bilans_poprz = suma_wplywow_poprz - suma_wydatkow_poprz
    
    delta_bilans = bilans - bilans_poprz
    delta_wplywy = suma_wplywow - suma_wplywow_poprz
    delta_wydatki = suma_wydatkow - suma_wydatkow_poprz
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Bilans Netto", f"{bilans:.2f} PLN", f"{delta_bilans:.2f} PLN m/m")
    m2.metric("Wpływy", f"{suma_wplywow:.2f} PLN", f"{delta_wplywy:.2f} PLN m/m")
    # delta_color="inverse" sprawia, że wzrost wydatków jest czerwony, a spadek zielony
    m3.metric("Wydatki", f"{suma_wydatkow:.2f} PLN", f"{delta_wydatki:.2f} PLN m/m", delta_color="inverse")
    
    st.write("")
    col_wykres1, col_wykres2 = st.columns([2, 1])
    
    with col_wykres1:
        st.markdown("**Cashflow (Wpływy vs Wydatki)**")
        full_range_dni = pd.date_range(start=aktywny_miesiac_start, end=aktywny_miesiac_koniec, freq='D')
        
        if not df_wybrany.empty:
            df_wybrany['Cashflow'] = df_wybrany.apply(lambda x: x['Kwota'] if x['Typ'] == 'Wpływ' else -x['Kwota'], axis=1)
            df_chart_bars = df_wybrany.groupby('Data_Tylko')['Cashflow'].sum().reset_index()
            
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
            # Rysowanie pustej siatki kalendarza, jeśli brakuje transakcji w danym miesiącu
            empty_days = pd.DataFrame({'Data_Tylko': full_range_dni, 'Cashflow': 0})
            bars = alt.Chart(empty_days).mark_bar(size=12).encode(
                x=alt.X('yearmonthdate(Data_Tylko):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                y=alt.Y('Cashflow:Q', title='PLN')
            )
            st.altair_chart(bars, use_container_width=True)
            
    with col_wykres2:
        st.markdown("**Struktura wydatków**")
        if not df_wybrany_wydatki.empty:
            donut = alt.Chart(df_wybrany_wydatki.groupby('Kategoria')['Kwota'].sum().reset_index()).mark_arc(innerRadius=45).encode(
                theta='Kwota:Q', 
                color=alt.Color('Kategoria:N', legend=alt.Legend(orient="bottom", title=None)), 
                tooltip=['Kategoria', alt.Tooltip('Kwota:Q', format='.2f', title='PLN')]
            ).properties(height=300)
            st.altair_chart(donut, use_container_width=True)
        else:
            st.info("Brak wydatków w wybranym miesiącu.")

    st.divider()
    st.markdown("**Historia operacji**")
    
    dostepne_kolumny = [col for col in ['Data', 'Typ', 'Kategoria', 'Kwota', 'Notatka'] if col in df.columns]
    
    # Wyświetlanie wszystkich wpisów, w przewijanym boksie z przypiętą wysokością 350px
    df_disp = df[dostepne_kolumny].iloc[::-1].copy()
    st.dataframe(df_disp.style.format({'Kwota': '{:.2f}'}), hide_index=True, use_container_width=True, height=350)

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
