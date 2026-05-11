import streamlit as st
import pandas as pd
import gspread
import altair as alt
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
        return sheet.get_all_records()
    
    # --- MODUŁ WPROWADZANIA DANYCH (SIDEBAR) ---
    with st.sidebar:
        st.header("Dodaj dane")
        with st.form("add_drink_form", clear_on_submit=True):
            nowa_data = st.date_input("Data spożycia", value=datetime.date.today())
            nowy_alko = st.selectbox("Rodzaj trunku", ["Piwo", "Wódka", "Wódka kolorowa", "Wino", "Inne"])
            nowa_ilosc = st.number_input("Ilość [ml]", min_value=0, step=50, value=500)
            nowa_moc = st.number_input("Moc [%]", min_value=0.0, step=0.1, value=5.0)
            
            submit_button = st.form_submit_button("Dodaj trunek")
            
            if submit_button:
                reverse_map = {'Wódka kolorowa': 'vk', 'Piwo': 'p', 'Wódka': 'v', 'Wino': 'w', 'Inne': 'i'}
                skrot_alko = reverse_map[nowy_alko]
                data_str = nowa_data.strftime('%d.%m.%Y')
                
                strefa_pl = ZoneInfo('Europe/Warsaw')
                nowy_czas = datetime.datetime.now(strefa_pl).strftime('%H:%M') 
                
                try:
                    # FIX: Tryb RAW zabrania arkuszom Google jakiejkolwiek interpretacji liczb (rozwiązuje problem z separatorem)
                    sheet.append_row(
                        [data_str, skrot_alko, float(nowa_ilosc), float(nowa_moc), nowy_czas], 
                        value_input_option='RAW'
                    )
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
                        strefa_pl = ZoneInfo('Europe/Warsaw')
                        aktualny_czas = datetime.datetime.now(strefa_pl).strftime('%H:%M')
                        
                        if len(ostatni_rekord) >= 5:
                            ostatni_rekord[4] = aktualny_czas
                        
                        sheet.append_row(ostatni_rekord, value_input_option='RAW')
                        st.success("Wprowadzono powielony rekord.")
                        fetch_data.clear() 
                        st.rerun()
                    else:
                        st.warning("Baza danych jest pusta.")
                except Exception as e:
                    st.error(f"Błąd: {e}")

    # --- POBIERANIE I CZYSZCZENIE DANYCH ---
    data = fetch_data()
    df = pd.DataFrame(data)

    df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').replace(' ', '').replace('', '0').astype(float)
    df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').str.replace('%', '').str.replace(' ', '').replace('', '0').astype(float)
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
    dzisiaj = pd.Timestamp.now(tz=ZoneInfo('Europe/Warsaw')).normalize().tz_localize(None)
    streak = (dzisiaj - ostatni_wpis).days
    if streak < 0: streak = 0 

    if streak == 0:
        st.error(f"Licznik trzeźwości: {streak} dni")
    elif streak == 1:
        st.warning(f"Licznik trzeźwości: {streak} dzień")
    else:
        st.success(f"Licznik trzeźwości: {streak} dni")

    col_top1, col_top2 = st.columns(2)

    with col_top1:
        st.subheader("Ostatnie wpisy")
        df_display = df.copy()
        df_display['Data_str'] = df_display['Data'].dt.strftime('%d.%m.%Y')
        kolumny_widoczne = ['Dzień tygodnia', 'Data_str', 'Godz.', 'Alkohol', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']
        df_display_final = df_display[kolumny_widoczne].tail(10).copy()
        df_display_final.columns = ['Dzień tygodnia', 'Data', 'Godz.', 'Alkohol', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']
        
        def highlight_alternating_dates(data):
            color_mask = data['Data'].factorize()[0] % 2 == 0
            return pd.DataFrame(
                [['background-color: rgba(255, 255, 255, 0.08)' if m else '' for _ in data.columns] for m in color_mask],
                index=data.index,
                columns=data.columns
            )
            
        styled_df = df_display_final.style.apply(highlight_alternating_dates, axis=None).format({
            'Ilość [ml]': '{:.0f}',
            'Moc [%]': '{:.1f}',
            'Czysty etanol [g]': '{:.1f}'
        })
        st.dataframe(styled_df, hide_index=True, use_container_width=True)

    with col_top2:
        st.subheader("Kalendarz Spożycia (Miesięczny)")
        
        if 'kalendarz_offset' not in st.session_state:
            st.session_state.kalendarz_offset = 0

        col_btn_l, col_miesiac, col_btn_r = st.columns([1, 2, 1])
        with col_btn_l:
            if st.button("Poprzedni"): st.session_state.kalendarz_offset -= 1
        with col_btn_r:
            if st.button("Następny"): st.session_state.kalendarz_offset += 1

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
        pelne_nazwy = {0: 'Poniedziałek', 1: 'Wtorek', 2: 'Środa', 3: 'Czwartek', 4: 'Piątek', 5: 'Sobota', 6: 'Niedziela'}
        df_kalendarz['Nazwa_dnia'] = df_kalendarz['Data'].dt.dayofweek.map(nazwy_krotkie)
        df_kalendarz['Pełny_dzień'] = df_kalendarz['Data'].dt.dayofweek.map(pelne_nazwy)
        df_kalendarz['Dzień_miesiąca'] = df_kalendarz['Data'].dt.day.astype(str)
        df_kalendarz['Rząd_tygodnia'] = df_kalendarz['Data'].apply(lambda d: (d.day - 1 + d.replace(day=1).weekday()) // 7)
        kolejnosc_kalendarza = ['Pon', 'Wto', 'Śro', 'Czw', 'Pią', 'Sob', 'Nie']
        
        kolorowanie = alt.condition(
            alt.datum['Etanol (g)'] == 0,
            alt.value('#27ae60'),
            alt.Color('Etanol (g):Q', scale=alt.Scale(scheme='reds'), legend=alt.Legend(title="Etanol (g)"))
        )
        heatmap = alt.Chart(df_kalendarz).mark_rect(stroke='gray', strokeWidth=0.5, cornerRadius=3).encode(
            x=alt.X('Nazwa_dnia:N', sort=kolejnosc_kalendarza, title=None),
            y=alt.Y('Rząd_tygodnia:O', title=None, axis=alt.Axis(labels=False, ticks=False)), 
            color=kolorowanie,
            tooltip=[alt.Tooltip('Data:T', format='%d.%m.%Y'), alt.Tooltip('Pełny_dzień:N', title='Dzień'), 'Etanol (g)']
        ).properties(height=250)
        
        text = alt.Chart(df_kalendarz).mark_text(baseline='middle').encode(
            x=alt.X('Nazwa_dnia:N', sort=kolejnosc_kalendarza),
            y=alt.Y('Rząd_tygodnia:O'),
            text=alt.Text('Dzień_miesiąca:N'),
            color=alt.condition(alt.datum['Etanol (g)'] > 60, alt.value('white'), alt.value('black'))
        )
        st.altair_chart(heatmap + text, use_container_width=True)

    st.subheader("Tygodnie")
    najblizsza_niedziela = dzisiaj + pd.Timedelta(days=(6 - dzisiaj.dayofweek))
    rok_temu_tydzien = najblizsza_niedziela - pd.Timedelta(days=364)
    df_52 = df[df['Data'] >= rok_temu_tydzien].copy()
    df_tygodnie = pd.DataFrame({'Tydzień_Offset': range(51, -1, -1)})
    df_tygodnie['Koniec_Tyg'] = najblizsza_niedziela - pd.to_timedelta(df_tygodnie['Tydzień_Offset'] * 7, unit='D')
    df_tygodnie['Poczatek_Tyg'] = df_tygodnie['Koniec_Tyg'] - pd.Timedelta(days=6)
    df_tygodnie['Zakres_Dat'] = df_tygodnie['Poczatek_Tyg'].dt.strftime('%d.%m') + " - " + df_tygodnie['Koniec_Tyg'].dt.strftime('%d.%m')
    
    if not df_52.empty:
        df_52['Tydzień_Offset'] = ((najblizsza_niedziela - df_52['Data']).dt.days // 7)
        weekly_sum = df_52.groupby('Tydzień_Offset')['Czysty etanol [g]'].sum().reset_index()
        df_heatmap_tyg = pd.merge(df_tygodnie, weekly_sum, on='Tydzień_Offset', how='left').fillna(0)
    else:
        df_heatmap_tyg = df_tygodnie.copy(); df_heatmap_tyg['Czysty etanol [g]'] = 0

    df_heatmap_tyg['Tydzień_Num'] = range(1, 53)
    df_heatmap_tyg['Wiersz'] = 'Postęp'
    df_heatmap_tyg = df_heatmap_tyg.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
    
    heatmap_tygodniowa = alt.Chart(df_heatmap_tyg).mark_rect(stroke='#2d303e', strokeWidth=1, cornerRadius=2).encode(
        x=alt.X('Tydzień_Num:O', title='Starsze tygodnie -> Aktualny tydzień', axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y('Wiersz:N', title=None, axis=alt.Axis(labels=False, ticks=False)), 
        color=alt.condition(alt.datum['Etanol (g)'] == 0, alt.value('#27ae60'), alt.Color('Etanol (g):Q', scale=alt.Scale(scheme='reds'))),
        tooltip=[alt.Tooltip('Zakres_Dat:N', title='Okres'), 'Etanol (g)']
    ).properties(height=80)
    st.altair_chart(heatmap_tygodniowa, use_container_width=True)

    st.divider()
    st.subheader("Panel (Ostatnie 30 dni)")
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    dwa_miesiace_temu = dzisiaj - pd.Timedelta(days=60)
    
    df_miesiac = df[df['Data'] >= miesiac_temu]
    df_poprzedni_miesiac = df[(df['Data'] >= dwa_miesiace_temu) & (df['Data'] < miesiac_temu)]

    if not df_miesiac.empty:
        total_etanol = df_miesiac['Czysty etanol [g]'].sum()
        eq_kufle = int(round(total_etanol / 19.725, 0))
        eq_shoty = int(round(total_etanol / 12.624, 0))
        eq_flaszki = round(total_etanol / 220.92, 1)
        
        total_etanol_poprzedni = df_poprzedni_miesiac['Czysty etanol [g]'].sum() if not df_poprzedni_miesiac.empty else 0
        eq_kufle_poprzednie = int(round(total_etanol_poprzedni / 19.725, 0))
        eq_shoty_poprzednie = int(round(total_etanol_poprzedni / 12.624, 0))
        eq_flaszki_poprzednie = round(total_etanol_poprzedni / 220.92, 1)
        
        delta_kufle = eq_kufle - eq_kufle_poprzednie
        delta_shoty = eq_shoty - eq_shoty_poprzednie
        delta_flaszki = round(eq_flaszki - eq_flaszki_poprzednie, 1)
        
        st.markdown("**Alkohol wypity w ostatnich 30 dniach w przeliczeniu na:**")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(label="Kufle piwa (5%)", value=eq_kufle, delta=int(delta_kufle), delta_color="inverse")
        kpi2.metric(label="Shoty wódki (40ml)", value=eq_shoty, delta=int(delta_shoty), delta_color="inverse")
        kpi3.metric(label="Flaszki 0.7 (40%)", value=eq_flaszki, delta=float(delta_flaszki), delta_color="inverse")
        
        st.divider()
        col1, col2 = st.columns([2, 1])
        kolory_alko = alt.Scale(domain=['Piwo', 'Wódka kolorowa', 'Wódka', 'Wino', 'Inne'], range=['#f1c40f', '#e84393', '#ffffff', '#e74c3c', '#95a5a6'])
        
        with col1:
            st.markdown("**Trend**")
            df_chart_bars = df_miesiac.groupby(['Data', 'Dzień tygodnia', 'Alkohol'])['Czysty etanol [g]'].sum().reset_index()
            df_chart_bars = df_chart_bars.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
            
            df_chart_line = df_miesiac.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
            full_range = pd.date_range(start=df_chart_line['Data'].min(), end=dzisiaj, freq='D')
            df_chart_line = df_chart_line.set_index('Data').reindex(full_range, fill_value=0).reset_index().rename(columns={'index': 'Data'})
            df_chart_line['Trend (7-dniowy)'] = df_chart_line['Czysty etanol [g]'].rolling(window=7, min_periods=1).mean()

            bars = alt.Chart(df_chart_bars).mark_bar(size=15).encode(
                x=alt.X('yearmonthdate(Data):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                y=alt.Y('Etanol (g):Q', title='Spożycie (g)'),
                color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(title="Trunek", orient="bottom")),
                tooltip=[alt.Tooltip('Data:T', format='%d.%m.%Y'), 'Dzień tygodnia', 'Alkohol', 'Etanol (g)']
            )
            line = alt.Chart(df_chart_line).mark_line(color='#3498db', size=3, interpolate='monotone').encode(x='yearmonthdate(Data):O', y='Trend (7-dniowy):Q')
            st.altair_chart(bars + line, use_container_width=True)
            
        with col2:
            st.markdown("**Struktura spożycia**")
            df_donut = df_miesiac.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
            donut = alt.Chart(df_donut.groupby('Alkohol')['Etanol (g)'].sum().reset_index()).mark_arc(innerRadius=50).encode(
                theta='Etanol (g):Q', color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(orient="bottom")), tooltip=['Alkohol', 'Etanol (g)']
            ).properties(height=350)
            st.altair_chart(donut, use_container_width=True)
    else:
        st.info("Brak danych z ostatnich 30 dni w rejestrze.")

    st.divider()
    st.subheader("Analiza Historyczna")
    tab1, tab2, tab3, tab4 = st.tabs(["Rozkład Tygodniowy", "Podsumowanie Miesięcy", "Top 3: Spożycie", "Top 3: Przerwy"])
    
    with tab1:
        df_dni = df.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        st.altair_chart(alt.Chart(df_dni.groupby('Dzień tygodnia')['Etanol (g)'].mean().round(1).reset_index()).mark_bar(color='#9b59b6').encode(
            x=alt.X('Dzień tygodnia:N', sort=kolejnosc_dni), y=alt.Y('Etanol (g):Q', title='Średnio etanolu (g)'), tooltip=['Dzień tygodnia', 'Etanol (g)']
        ).properties(height=300), use_container_width=True)

    with tab2:
        df_m = df[df['Miesiąc'] != 'Kwiecień'].rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        df_m = df_m.groupby('Miesiąc')['Etanol (g)'].mean().round(1).reset_index()
        st.altair_chart((alt.Chart(df_m).mark_bar(color='#f39c12').encode(x=alt.X('Miesiąc:N', sort=kolejnosc_miesiecy), y=alt.Y('Etanol (g):Q', title='Średnio etanolu (g)'), tooltip=['Miesiąc', 'Etanol (g)']) + 
                         alt.Chart(df_m).mark_line(color='#e74c3c', size=3, interpolate='monotone').encode(x=alt.X('Miesiąc:N', sort=kolejnosc_miesiecy), y='Etanol (g):Q')
                        ).properties(height=300), use_container_width=True)

    with tab3:
        df_p = df.groupby(['Data', 'Dzień tygodnia'])['Czysty etanol [g]'].sum().reset_index().sort_values(by='Czysty etanol [g]', ascending=False).head(3)
        for i, r in df_p.iterrows():
            st.markdown(f"### {r['Data'].strftime('%d.%m.%Y')} ({r['Dzień tygodnia']}) - {r['Czysty etanol [g]']}g")
            st.divider()

    with tab4:
        u_d = df['Data'].dt.normalize().drop_duplicates().sort_values().reset_index(drop=True)
        gaps = []
        for i in range(1, len(u_d)):
            d = (u_d[i] - u_d[i-1]).days - 1
            if d > 0: gaps.append({'Dni': d, 'Okres': f"{(u_d[i-1]+pd.Timedelta(days=1)).strftime('%d.%m')} - {(u_d[i]-pd.Timedelta(days=1)).strftime('%d.%m')}"})
        if not u_d.empty and (dzisiaj - u_d.iloc[-1]).days > 0:
            gaps.append({'Dni': (dzisiaj - u_d.iloc[-1]).days, 'Okres': f"{(u_d.iloc[-1]+pd.Timedelta(days=1)).strftime('%d.%m')} - Dziś (Trwa)"})
        for g in sorted(gaps, key=lambda x: x['Dni'], reverse=True)[:3]:
            st.markdown(f"### {g['Dni']} dni ({g['Okres']})"); st.divider()

except Exception as e:
    st.error(f"Błąd krytyczny układu logiki: {e}")
