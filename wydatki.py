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

# --- MAPOWANIE KOLORÓW KATEGORII ---
PALETA_KATEGORII = alt.Scale(
    domain=["JEDZENIE", "NAPOJE", "ALKOHOL", "SNUSY", "ROZRYWKA", "KOMUNIKACJA", "KOSZTY STAŁE", "XTB", "NA PÓŹNIEJ", "INNE"],
    range=["#e67e22", "#f1c40f", "#3498db", "#9b59b6", "#2ecc71", "#bdc3c7", "#7f8c8d", "#e74c3c", "#ecf0f1", "#95a5a6"]
)

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

    dzisiaj = pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).normalize().tz_localize(None)
    pierwszy_dzien_obecnego = dzisiaj.replace(day=1)
    
    aktywny_miesiac_start = pierwszy_dzien_obecnego + pd.DateOffset(months=st.session_state.miesiac_offset)
    aktywny_miesiac_koniec = aktywny_miesiac_start + pd.DateOffset(months=1) - pd.Timedelta(days=1)
    poprzedni_miesiac_start = aktywny_miesiac_start - pd.DateOffset(months=1)

    miesiace_pl = ['Styczeń', 'Luty', 'Marzec', 'Kwiecień', 'Maj', 'Czerwiec', 'Lipiec', 'Sierpień', 'Wrzesień', 'Październik', 'Listopad', 'Grudzień']
    nazwa_miesiaca = f"{miesiace_pl[aktywny_miesiac_start.month - 1]} {aktywny_miesiac_start.year}"
    nazwa_poprzedniego = f"{miesiace_pl[poprzedni_miesiac_start.month - 1]} {poprzedni_miesiac_start.year}"
    
    with c2: 
        st.markdown(f"<h4 style='text-align: center; margin-top: 0;'>{nazwa_miesiaca}</h4>", unsafe_allow_html=True)
    
    df_wybrany = df[(df['Data_Tylko'] >= aktywny_miesiac_start) & (df['Data_Tylko'] <= aktywny_miesiac_koniec)].copy()
    df_poprzedni = df[(df['Data_Tylko'] >= poprzedni_miesiac_start) & (df['Data_Tylko'] < aktywny_miesiac_start)].copy()
    
    df_wybrany_wydatki = df_wybrany[df_wybrany['Typ'] == 'Wydatek']
    df_wybrany_wplywy = df_wybrany[df_wybrany['Typ'] == 'Wpływ']
    
    suma_wydatkow = df_wybrany_wydatki['Kwota'].sum()
    suma_wplywow = df_wybrany_wplywy['Kwota'].sum()
    bilans = suma_wplywow - suma_wydatkow
    
    suma_wydatkow_poprz = df_poprzedni[df_poprzedni['Typ'] == 'Wydatek']['Kwota'].sum()
    suma_wplywow_poprz = df_poprzedni[df_poprzedni['Typ'] == 'Wpływ']['Kwota'].sum()
    bilans_poprz = suma_wplywow_poprz - suma_wydatkow_poprz
    
    delta_bilans = bilans - bilans_poprz
    delta_wplywy = suma_wplywow - suma_wplywow_poprz
    delta_wydatki = suma_wydatkow - suma_wydatkow_poprz
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Bilans Netto", f"{bilans:.2f} PLN", f"{delta_bilans:.2f} PLN m/m")
    m2.metric("Wpływy", f"{suma_wplywow:.2f} PLN", f"{delta_wplywy:.2f} PLN m/m")
    m3.metric("Wydatki", f"{suma_wydatkow:.2f} PLN", f"{delta_wydatki:.2f} PLN m/m", delta_color="inverse")
    
    st.write("")
    col_wykres1, col_wykres2 = st.columns([2, 1])
    
    with col_wykres1:
        st.markdown("**Cashflow (Wpływy vs Wydatki)**")
        full_range_dni = pd.date_range(start=aktywny_miesiac_start, end=aktywny_miesiac_koniec, freq='D')
        
        if not df_wybrany.empty:
            df_wykres = df_wybrany.copy()
            df_wykres['Wartość'] = df_wykres.apply(lambda x: x['Kwota'] if x['Typ'] == 'Wpływ' else -x['Kwota'], axis=1)
            
            df_chart_bars = df_wykres.groupby(['Data_Tylko', 'Typ'])['Wartość'].sum().reset_index()
            
            empty_days = pd.DataFrame({'Data_Tylko': full_range_dni, 'Typ': 'Wpływ', 'Wartość': 0})
            df_chart_bars = pd.concat([df_chart_bars, empty_days]).groupby(['Data_Tylko', 'Typ'])['Wartość'].sum().reset_index()
            
            domain = ['Wpływ', 'Wydatek']
            range_colors = ['#2ecc71', '#e74c3c']

            bars = alt.Chart(df_chart_bars).mark_bar(size=12).encode(
                x=alt.X('yearmonthdate(Data_Tylko):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                y=alt.Y('Wartość:Q', title='PLN'),
                color=alt.Color('Typ:N', scale=alt.Scale(domain=domain, range=range_colors), legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[
                    alt.Tooltip('Data_Tylko:T', format='%d.%m.%Y', title='Data'),
                    alt.Tooltip('Typ:N', title='Rodzaj'),
                    alt.Tooltip('Wartość:Q', title='PLN', format='.2f')
                ]
            )
            st.altair_chart(bars, use_container_width=True)
        else:
            empty_days = pd.DataFrame({'Data_Tylko': full_range_dni, 'Wartość': 0})
            bars = alt.Chart(empty_days).mark_bar(size=12).encode(
                x=alt.X('yearmonthdate(Data_Tylko):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                y=alt.Y('Wartość:Q', title='PLN')
            )
            st.altair_chart(bars, use_container_width=True)
            
    with col_wykres2:
        st.markdown("**Struktura wydatków**")
        if not df_wybrany_wydatki.empty:
            donut = alt.Chart(df_wybrany_wydatki.groupby('Kategoria')['Kwota'].sum().reset_index()).mark_arc(innerRadius=45).encode(
                theta='Kwota:Q', 
                color=alt.Color('Kategoria:N', scale=PALETA_KATEGORII, legend=alt.Legend(orient="bottom", title=None, columns=2)), 
                tooltip=['Kategoria', alt.Tooltip('Kwota:Q', format='.2f', title='PLN')]
            ).properties(height=380)
            st.altair_chart(donut, use_container_width=True)
        else:
            st.info("Brak wydatków w wybranym miesiącu.")

    # --- NOWA SEKCJA: PORÓWNANIE MIESIĄC DO MIESIĄCA ---
    st.write("")
    st.markdown(f"**Porównanie wydatków: {nazwa_miesiaca} vs {nazwa_poprzedniego}**")
    
    df_wybrany_wyd_copy = df_wybrany_wydatki.copy()
    df_wybrany_wyd_copy['Okres'] = 'Wybrany miesiąc'
    
    df_poprzedni_wyd_copy = df_poprzedni[df_poprzedni['Typ'] == 'Wydatek'].copy()
    df_poprzedni_wyd_copy['Okres'] = 'Poprzedni miesiąc'
    
    df_porownanie = pd.concat([df_wybrany_wyd_copy, df_poprzedni_wyd_copy])
    
    if not df_porownanie.empty:
        df_porownanie_grouped = df_porownanie.groupby(['Okres', 'Kategoria'])['Kwota'].sum().reset_index()
        
        # Sortowanie według wydatków obecnego miesiąca, żeby te największe były na start
        sort_porownanie = df_wybrany_wyd_copy.groupby('Kategoria')['Kwota'].sum().sort_values(ascending=False).index.tolist()
        missing_cats = [c for c in df_porownanie_grouped['Kategoria'].unique() if c not in sort_porownanie]
        sort_porownanie.extend(missing_cats)
        
        bars_compare = alt.Chart(df_porownanie_grouped).mark_bar(size=12).encode(
            x=alt.X('Kategoria:N', sort=sort_porownanie, title=None, axis=alt.Axis(labelAngle=-45)),
            xOffset=alt.XOffset('Okres:N', sort=['Poprzedni miesiąc', 'Wybrany miesiąc']),
            y=alt.Y('Kwota:Q', title='PLN'),
            color=alt.Color('Okres:N', scale=alt.Scale(domain=['Poprzedni miesiąc', 'Wybrany miesiąc'], range=['#7f8c8d', '#3498db']), legend=alt.Legend(title=None, orient="bottom")),
            tooltip=[alt.Tooltip('Kategoria:N', title='Kategoria'), alt.Tooltip('Okres:N', title='Okres'), alt.Tooltip('Kwota:Q', title='PLN', format='.2f')]
        ).properties(height=350)
        st.altair_chart(bars_compare, use_container_width=True)
    else:
        st.info("Brak danych do porównania z poprzednim miesiącem.")

    # --- NOWA SEKCJA: TRENDY ---
    st.divider()
    st.subheader("Trendy w czasie")
    widok_wykresu = st.radio("Zmień zakres czasu:", ["Dzienny (ostatnie 30 dni)", "Tygodniowy (cała historia)", "Miesięczny (cała historia)"], horizontal=True)

    if widok_wykresu == "Dzienny (ostatnie 30 dni)":
        start_date = dzisiaj - pd.Timedelta(days=30)
        df_trend = df[df['Data_Tylko'] >= start_date].copy()
        df_trend['Okres'] = df_trend['Data_Tylko']
        x_format = '%d.%m'
        x_title = 'Data'
        wygładzanie_span = 14
    elif widok_wykresu == "Tygodniowy (cała historia)":
        df_trend = df.copy()
        df_trend['Okres'] = df_trend['Data_Tylko'] - pd.to_timedelta(df_trend['Data_Tylko'].dt.dayofweek, unit='D')
        x_format = '%d.%m.%Y'
        x_title = 'Tydzień (od poniedziałku)'
        wygładzanie_span = 4
    else:
        df_trend = df.copy()
        df_trend['Okres'] = df_trend['Data_Tylko'] - pd.to_timedelta(df_trend['Data_Tylko'].dt.day - 1, unit='D')
        x_format = '%m.%Y'
        x_title = 'Miesiąc'
        wygładzanie_span = 3

    if not df_trend.empty:
        df_cf = df_trend.copy()
        df_cf['Wartość'] = df_cf.apply(lambda x: x['Kwota'] if x['Typ'] == 'Wpływ' else -x['Kwota'], axis=1)
        df_cf_grouped = df_cf.groupby(['Okres', 'Typ'])['Wartość'].sum().reset_index()
        
        df_kat = df_trend[df_trend['Typ'] == 'Wydatek'].copy()
        df_kat_grouped = df_kat.groupby(['Okres', 'Kategoria'])['Kwota'].sum().reset_index()

        if widok_wykresu == "Dzienny (ostatnie 30 dni)":
            full_range = pd.date_range(start=start_date, end=dzisiaj, freq='D')
            empty_cf = pd.DataFrame({'Okres': full_range, 'Typ': 'Wpływ', 'Wartość': 0})
            df_cf_grouped = pd.concat([df_cf_grouped, empty_cf]).groupby(['Okres', 'Typ'])['Wartość'].sum().reset_index()
            
            empty_kat = pd.DataFrame({'Okres': full_range, 'Kategoria': 'INNE', 'Kwota': 0})
            df_kat_grouped = pd.concat([df_kat_grouped, empty_kat]).groupby(['Okres', 'Kategoria'])['Kwota'].sum().reset_index()

        st.write("")
        st.markdown("**Cashflow (Wpływy vs Wydatki)**")
        bars_cf = alt.Chart(df_cf_grouped).mark_bar(size=12).encode(
            x=alt.X('yearmonthdate(Okres):O', title=x_title, axis=alt.Axis(format=x_format, labelAngle=-90)),
            y=alt.Y('Wartość:Q', title='PLN'),
            color=alt.Color('Typ:N', scale=alt.Scale(domain=['Wpływ', 'Wydatek'], range=['#2ecc71', '#e74c3c']), legend=alt.Legend(title=None, orient="bottom")),
            tooltip=[alt.Tooltip('Okres:T', format=x_format, title='Okres'), alt.Tooltip('Typ:N', title='Rodzaj'), alt.Tooltip('Wartość:Q', title='PLN', format='.2f')]
        )
        st.altair_chart(bars_cf, use_container_width=True)

        st.write("")
        st.markdown("**Struktura wydatków w czasie**")
        if not df_kat_grouped.empty and df_kat_grouped['Kwota'].sum() > 0:
            bars_kat = alt.Chart(df_kat_grouped).mark_bar().encode(
                x=alt.X('yearmonthdate(Okres):O', title=x_title, axis=alt.Axis(format=x_format, labelAngle=-90)),
                y=alt.Y('Kwota:Q', title='PLN'),
                color=alt.Color('Kategoria:N', scale=PALETA_KATEGORII, legend=alt.Legend(title=None, orient="bottom", columns=2)),
                tooltip=[alt.Tooltip('Okres:T', format=x_format, title='Okres'), alt.Tooltip('Kategoria:N', title='Kategoria'), alt.Tooltip('Kwota:Q', title='PLN', format='.2f')]
            )
            
            df_line = df_kat_grouped.groupby('Okres')['Kwota'].sum().reset_index()
            df_line['Trend'] = df_line['Kwota'].ewm(span=wygładzanie_span, adjust=False).mean()
            line_kat = alt.Chart(df_line).mark_line(color='#3498db', size=3, interpolate='monotone').encode(
                x=alt.X('yearmonthdate(Okres):O'),
                y=alt.Y('Trend:Q')
            )
            st.altair_chart((bars_kat + line_kat).properties(height=380), use_container_width=True)
        else:
            st.info("Brak wydatków w tym widoku.")
    else:
        st.info("Brak danych w historii.")

    # --- NOWA SEKCJA: ŚREDNIE MIESIĘCZNE ---
    st.divider()
    st.markdown("**Średnie miesięczne wydatki wg kategorii (cała historia)**")
    
    df_wydatki_wszystkie = df[df['Typ'] == 'Wydatek'].copy()
    if not df_wydatki_wszystkie.empty:
        liczba_miesiecy = df['Data_Tylko'].dt.to_period('M').nunique()
        
        df_srednie = df_wydatki_wszystkie.groupby('Kategoria')['Kwota'].sum().reset_index()
        df_srednie['Średnia'] = df_srednie['Kwota'] / max(1, liczba_miesiecy)
        
        # Wymuszenie fizycznego sortowania od największego do najmniejszego
        df_srednie = df_srednie.sort_values(by='Średnia', ascending=False)
        sort_order_srednie = df_srednie['Kategoria'].tolist()

        bars_avg = alt.Chart(df_srednie).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X('Średnia:Q', title='Średnio PLN / miesiąc', axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y('Kategoria:N', sort=sort_order_srednie, title=None),
            color=alt.Color('Kategoria:N', scale=PALETA_KATEGORII, legend=None),
            tooltip=[alt.Tooltip('Kategoria:N', title='Kategoria'), alt.Tooltip('Średnia:Q', title='Średnio (PLN/msc)', format='.2f')]
        )
        
        text_avg = bars_avg.mark_text(
            align='left',
            baseline='middle',
            dx=5,
            color='white'
        ).encode(
            text=alt.Text('Średnia:Q', format='.2f')
        )
        
        st.altair_chart((bars_avg + text_avg).properties(height=alt.Step(35)), use_container_width=True)
    else:
        st.info("Brak wydatków do podsumowania.")

    st.divider()
    st.markdown("**Historia operacji**")
    
    dostepne_kolumny = [col for col in ['Data', 'Typ', 'Kategoria', 'Kwota', 'Notatka'] if col in df.columns]
    
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
