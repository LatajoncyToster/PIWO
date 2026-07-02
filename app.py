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
        kolejnosc_kalendarza = ['Pon', 'Wto', 'Śro', 'Czw', 'Pią', 'Sob', 'Nie']

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
            txt = f"Licznik trzeźwości: {streak} dni"

        st.markdown(f'''
        <div style="background-color: {c_bg}; color: {c_text}; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; border: 1px solid {c_text}40;">
            {txt}
        </div>
        ''', unsafe_allow_html=True)

        col_top1, col_top2 = st.columns(2)

        with col_top1:
            st.subheader("Ostatnie wpisy")
            df_disp = df.copy()
            df_disp['Data_str'] = df_disp['Data'].dt.strftime('%d.%m.%Y')
            
            df_final = df_disp[['Dzień tygodnia', 'Data_str', 'Godz.', 'Alkohol', 'Opis', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']].iloc[::-1].copy()
            df_final.columns = ['Dzień tygodnia', 'Data', 'Godz.', 'Alkohol', 'Opis', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']
            
            def highlight_dates(data):
                mask = data['Data'].factorize()[0] % 2 == 0
                return pd.DataFrame([['background-color: rgba(255, 255, 255, 0.08)' if m else '' for _ in data.columns] for m in mask], index=data.index, columns=data.columns)
                
            st.dataframe(
                df_final.style.apply(highlight_dates, axis=None).format({'Ilość [ml]': '{:.0f}', 'Moc [%]': '{:.1f}', 'Czysty etanol [g]': '{:.1f}'}), 
                hide_index=True, 
                use_container_width=True, 
                height=350
            )

        with col_top2:
            st.subheader("Kalendarz (Miesięczny)")
            if 'kalendarz_offset' not in st.session_state: st.session_state.kalendarz_offset = 0
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1: 
                if st.button("Poprzedni"): st.session_state.kalendarz_offset -= 1
            with c3:
                if st.button("Następny"): st.session_state.kalendarz_offset += 1
            aktywna = dzisiaj + pd.DateOffset(months=st.session_state.kalendarz_offset)
            with c2: 
                st.markdown(f"<h4 style='text-align: center;'>{aktywna.strftime('%m.%Y')}</h4>", unsafe_allow_html=True)
            
            dni_m = pd.date_range(start=aktywna.replace(day=1), end=(aktywna.replace(day=1) + pd.DateOffset(months=1)) - pd.Timedelta(days=1), freq='D')
            df_k = pd.DataFrame({'Data': dni_m}).merge(df.groupby('Data')['Czysty etanol [g]'].sum().reset_index(), on='Data', how='left').fillna(0)
            df_k = df_k.rename(columns={'Czysty etanol [g]': 'Etanol'})
            
            nazwy_krotkie = {0: 'Pon', 1: 'Wto', 2: 'Śro', 3: 'Czw', 4: 'Pią', 5: 'Sob', 6: 'Nie'}
            pelne_nazwy = {0: 'Poniedziałek', 1: 'Wtorek', 2: 'Środa', 3: 'Czwartek', 4: 'Piątek', 5: 'Sobota', 6: 'Niedziela'}
            df_k['Nazwa_dnia'] = df_k['Data'].dt.dayofweek.map(nazwy_krotkie)
            df_k['Pełny_dzień'] = df_k['Data'].dt.dayofweek.map(pelne_nazwy)
            df_k['Dzień_miesiąca'] = df_k['Data'].dt.day.astype(str)
            df_k['Rząd_tygodnia'] = df_k['Data'].apply(lambda d: (d.day - 1 + d.replace(day=1).weekday()) // 7)
            
            kolorowanie = alt.condition(
                alt.datum['Etanol'] == 0,
                alt.value('#27ae60'),
                alt.Color('Etanol:Q', scale=alt.Scale(scheme='reds'), legend=alt.Legend(title="Etanol (g)"))
            )
            heatmap = alt.Chart(df_k).mark_rect(stroke='gray', strokeWidth=0.5, cornerRadius=3).encode(
                x=alt.X('Nazwa_dnia:N', sort=kolejnosc_kalendarza, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Rząd_tygodnia:O', title=None, axis=alt.Axis(labels=False, ticks=False)), 
                color=kolorowanie,
                tooltip=[alt.Tooltip('Data:T', format='%d.%m.%Y'), alt.Tooltip('Pełny_dzień:N', title='Dzień'), alt.Tooltip('Etanol:Q', title='Etanol (g)')]
            ).properties(height=250)
            
            text = alt.Chart(df_k).mark_text(baseline='middle').encode(
                x=alt.X('Nazwa_dnia:N', sort=kolejnosc_kalendarza),
                y=alt.Y('Rząd_tygodnia:O'),
                text=alt.Text('Dzień_miesiąca:N'),
                color=alt.condition(alt.datum['Etanol'] > 60, alt.value('white'), alt.value('black'))
            )
            st.altair_chart(heatmap + text, use_container_width=True)

        st.divider()
        # ZMIANA: Usunięto subheader Tygodnie i dodano nowy Panel Główny z przełącznikiem
        st.subheader("Panel Główny")
        miesiac_temu = dzisiaj - pd.Timedelta(days=30)
        dwa_miesiace_temu = dzisiaj - pd.Timedelta(days=60)
        
        df_miesiac = df[df['Data'] >= miesiac_temu]
        df_poprzedni_miesiac = df[(df['Data'] >= dwa_miesiace_temu) & (df['Data'] < miesiac_temu)]

        if not df_miesiac.empty:
            total_etanol = df_miesiac['Czysty etanol [g]'].sum()
            eq_kufle = int(round(total_etanol / 19.725, 0))
            eq_shoty = int(round(total_etanol / 12.624, 0))
            eq_flaszki = round(total_etanol / 315.6, 2)
            
            total_etanol_poprzedni = df_poprzedni_miesiac['Czysty etanol [g]'].sum() if not df_poprzedni_miesiac.empty else 0
            eq_kufle_poprzednie = int(round(total_etanol_poprzedni / 19.725, 0))
            eq_shoty_poprzednie = int(round(total_etanol_poprzedni / 12.624, 0))
            eq_flaszki_poprzednie = round(total_etanol_poprzedni / 315.6, 2)
            
            delta_kufle = eq_kufle - eq_kufle_poprzednie
            delta_shoty = eq_shoty - eq_shoty_poprzednie
            delta_flaszki = round(eq_flaszki - eq_flaszki_poprzednie, 2)
            
            st.markdown("**Alkohol wypity w ostatnich 30 dniach w przeliczeniu na:**")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric(label="Puszki piwa (5%)", value=eq_kufle, delta=int(delta_kufle), delta_color="inverse")
            kpi2.metric(label="Shoty wódki (40ml)", value=eq_shoty, delta=int(delta_shoty), delta_color="inverse")
            kpi3.metric(label="Litry wódki (40%)", value=eq_flaszki, delta=float(delta_flaszki), delta_color="inverse")
            
            st.divider()
            
            # ZMIANA: Implementacja dynamicznego wyboru widoku trendu
            widok_wykresu = st.radio("Zmień widok trendu:", ["Dzienny (ostatnie 30 dni)", "Tygodniowy (cała historia)"], horizontal=True)
            st.write("") # Odstęp
            
            col1, col2 = st.columns([2, 1])
            kolory_alko = alt.Scale(domain=['Piwo', 'Wódka kolorowa', 'Wódka', 'Wino', 'Inne'], range=['#f1c40f', '#e84393', '#ffffff', '#e74c3c', '#95a5a6'])
            
            with col1:
                st.markdown("**Trend spożycia**")
                if widok_wykresu == "Dzienny (ostatnie 30 dni)":
                    df_chart_bars = df_miesiac.groupby(['Data', 'Alkohol'])['Czysty etanol [g]'].sum().reset_index()
                    df_chart_bars = df_chart_bars.rename(columns={'Czysty etanol [g]': 'Etanol'})
                    
                    df_chart_line = df_miesiac.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
                    full_range = pd.date_range(start=df_chart_line['Data'].min(), end=dzisiaj, freq='D')
                    df_chart_line = df_chart_line.set_index('Data').reindex(full_range, fill_value=0).reset_index().rename(columns={'index': 'Data'})
                    df_chart_line['Trend'] = df_chart_line['Czysty etanol [g]'].ewm(span=5, adjust=False).mean()

                    bars = alt.Chart(df_chart_bars).mark_bar(size=15).encode(
                        x=alt.X('yearmonthdate(Data):O', title='Data', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                        y=alt.Y('Etanol:Q', title='Spożycie (g)'),
                        color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(title="Trunek", orient="bottom")),
                        tooltip=[alt.Tooltip('Data:T', format='%d.%m.%Y', title='Data'), 'Alkohol', alt.Tooltip('Etanol:Q', title='Etanol (g)')]
                    )
                    
                    line = alt.Chart(df_chart_line).mark_line(color='#3498db', size=3, interpolate='monotone').encode(
                        x=alt.X('yearmonthdate(Data):O'), 
                        y=alt.Y('Trend:Q')
                    )
                    st.altair_chart(bars + line, use_container_width=True)
                    
                else:
                    df_tyg = df.copy()
                    df_tyg['Tydzień'] = df_tyg['Data'].dt.normalize() - pd.to_timedelta(df_tyg['Data'].dt.dayofweek, unit='D')
                    df_chart_bars = df_tyg.groupby(['Tydzień', 'Alkohol'])['Czysty etanol [g]'].sum().reset_index()
                    df_chart_bars = df_chart_bars.rename(columns={'Czysty etanol [g]': 'Etanol'})
                    
                    df_chart_line = df_tyg.groupby('Tydzień')['Czysty etanol [g]'].sum().reset_index()
                    if not df_chart_line.empty:
                        koniec_poniedzialek = (dzisiaj - pd.to_timedelta(dzisiaj.dayofweek, unit='D')).normalize()
                        full_range = pd.date_range(start=df_chart_line['Tydzień'].min(), end=koniec_poniedzialek, freq='7D')
                        df_chart_line = df_chart_line.set_index('Tydzień').reindex(full_range, fill_value=0).reset_index().rename(columns={'index': 'Tydzień'})
                        df_chart_line['Trend'] = df_chart_line['Czysty etanol [g]'].ewm(span=3, adjust=False).mean()
                    else:
                        df_chart_line['Trend'] = pd.Series(dtype=float)

                    bars = alt.Chart(df_chart_bars).mark_bar(size=20).encode(
                        x=alt.X('yearmonthdate(Tydzień):O', title='Tydzień (od poniedziałku)', axis=alt.Axis(format='%d.%m', labelAngle=-90)),
                        y=alt.Y('Etanol:Q', title='Spożycie (g)'),
                        color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(title="Trunek", orient="bottom")),
                        tooltip=[alt.Tooltip('Tydzień:T', format='%d.%m.%Y', title='Tydzień od'), 'Alkohol', alt.Tooltip('Etanol:Q', title='Etanol (g)')]
                    )
                    
                    line = alt.Chart(df_chart_line).mark_line(color='#3498db', size=3, interpolate='monotone').encode(
                        x=alt.X('yearmonthdate(Tydzień):O'), 
                        y=alt.Y('Trend:Q')
                    )
                    st.altair_chart(bars + line, use_container_width=True)
                
            with col2:
                st.markdown("**Struktura spożycia**")
                # ZMIANA: Wykres kołowy dostosowuje się do wybranego przedziału czasowego
                if widok_wykresu == "Dzienny (ostatnie 30 dni)":
                    df_donut = df_miesiac.rename(columns={'Czysty etanol [g]': 'Etanol'})
                else:
                    df_donut = df.rename(columns={'Czysty etanol [g]': 'Etanol'})
                    
                donut = alt.Chart(df_donut.groupby('Alkohol')['Etanol'].sum().reset_index()).mark_arc(innerRadius=50).encode(
                    theta='Etanol:Q', 
                    color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(orient="bottom")), 
                    tooltip=['Alkohol', alt.Tooltip('Etanol:Q', format='.1f', title='Etanol (g)')]
                ).properties(height=350)
                st.altair_chart(donut, use_container_width=True)
        else:
            st.info("Brak danych z ostatnich 30 dni w rejestrze.")

        st.divider()
        st.subheader("Analiza Historyczna")
        
        def odmiana(n, f1, f2, f3):
            if n == 1: return f"{n} {f1}"
            if 10 < n % 100 < 15: return f"{n} {f3}"
            if n % 10 in [2, 3, 4]: return f"{n} {f2}"
            return f"{n} {f3}"
            
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Rozkład Tygodniowy", "Podsumowanie Miesięcy", "Top 3: Spożycie", "Top 3: Przerwy", "Ciągi"])
        
        with tab1:
            df_dni = df.rename(columns={'Czysty etanol [g]': 'Etanol'})
            st.altair_chart(alt.Chart(df_dni.groupby('Dzień tygodnia')['Etanol'].mean().round(1).reset_index()).mark_bar(color='#9b59b6').encode(
                x=alt.X('Dzień tygodnia:N', sort=kolejnosc_dni), 
                y=alt.Y('Etanol:Q', title='Średnio etanolu (g)'), 
                tooltip=['Dzień tygodnia', alt.Tooltip('Etanol:Q', title='Etanol (g)')]
            ).properties(height=300), use_container_width=True)

        with tab2:
            df_m = df[df['Miesiąc'] != 'Kwiecień'].rename(columns={'Czysty etanol [g]': 'Etanol'})
            df_m = df_m.groupby('Miesiąc')['Etanol'].mean().round(1).reset_index()
            st.altair_chart((alt.Chart(df_m).mark_bar(color='#f39c12').encode(
                                x=alt.X('Miesiąc:N', sort=kolejnosc_miesiecy), 
                                y=alt.Y('Etanol:Q', title='Średnio etanolu (g)'), 
                                tooltip=['Miesiąc', alt.Tooltip('Etanol:Q', title='Etanol (g)')]) + 
                             alt.Chart(df_m).mark_line(color='#e74c3c', size=3, interpolate='monotone').encode(
                                x=alt.X('Miesiąc:N', sort=kolejnosc_miesiecy), 
                                y='Etanol:Q')
                            ).properties(height=300), use_container_width=True)

        with tab3:
            df_p = df.groupby(['Data', 'Dzień tygodnia'])['Czysty etanol [g]'].sum().reset_index()
            df_p = df_p.sort_values(by='Czysty etanol [g]', ascending=False).head(3)
            
            for i, (_, r) in enumerate(df_p.iterrows()):
                g = round(r['Czysty etanol [g]'], 1)
                ilosc_piw = int(round(g/19.725, 0))
                txt_piwa = odmiana(ilosc_piw, "piwo", "piwa", "piw")
                
                st.write(f"**{i+1}. {r['Data'].strftime('%d.%m.%Y')} ({r['Dzień tygodnia']})**")
                st.write(f"Etanol: {g}g | {txt_piwa}")
                st.write("---")

        with tab4:
            u_d = df['Data'].dt.normalize().drop_duplicates().sort_values().reset_index(drop=True)
            gaps = []
            for i in range(1, len(u_d)):
                d = (u_d[i] - u_d[i-1]).days - 1
                if d > 0: 
                    gaps.append({'d': d, 'ok': f"{(u_d[i-1]+pd.Timedelta(days=1)).strftime('%d.%m')} - {(u_d[i]-pd.Timedelta(days=1)).strftime('%d.%m')}"})
            
            if not u_d.empty and (dzisiaj - u_d.iloc[-1]).days > 0:
                gaps.append({'d': (dzisiaj - u_d.iloc[-1]).days, 'ok': f"{(u_d.iloc[-1]+pd.Timedelta(days=1)).strftime('%d.%m')} - Dziś (Trwa)"})
            
            for i, g in enumerate(sorted(gaps, key=lambda x: x['d'], reverse=True)[:3]):
                st.write(f"**{i+1}. {g['d']} dni** ({g['ok']})")
                st.write("---")

        with tab5:
            u_d_drink = df['Data'].dt.normalize().drop_duplicates().sort_values().reset_index(drop=True)
            drinking_streaks = []
            if not u_d_drink.empty:
                df_daily_etanol = df.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
                etanol_map = dict(zip(df_daily_etanol['Data'], df_daily_etanol['Czysty etanol [g]']))
                
                curr_streak = [u_d_drink.iloc[0]]
                for i in range(1, len(u_d_drink)):
                    if (u_d_drink.iloc[i] - u_d_drink.iloc[i-1]).days == 1:
                        curr_streak.append(u_d_drink.iloc[i])
                    else:
                        drinking_streaks.append(curr_streak)
                        curr_streak = [u_d_drink.iloc[i]]
                drinking_streaks.append(curr_streak)
                
                streak_gaps = []
                for s in drinking_streaks:
                    total_s_etanol = sum(etanol_map.get(date, 0) for date in s)
                    avg_s_etanol = total_s_etanol / len(s)
                    avg_s_beers = avg_s_etanol / 19.725
                    
                    streak_gaps.append({
                        'd': len(s), 
                        'ok': f"{s[0].strftime('%d.%m')} - {s[-1].strftime('%d.%m')}" if len(s) > 1 else f"{s[0].strftime('%d.%m')}",
                        'avg_g': round(avg_s_etanol, 1),
                        'avg_p': round(avg_s_beers, 1)
                    })
                
                for i, g in enumerate(sorted(streak_gaps, key=lambda x: x['d'], reverse=True)[:3]):
                    txt_dni = odmiana(g['d'], "dzień", "dni", "dni")
                    txt_piwa = odmiana(int(round(g['avg_p'], 0)), "piwo", "piwa", "piw")
                    
                    st.write(f"**{i+1}. {txt_dni}** ({g['ok']})")
                    st.write(f"Średnio na dzień: {g['avg_g']}g etanolu | {txt_piwa}")
                    st.write("---")
            else:
                st.info("Brak danych.")

    else:
        st.warning("Brak wpisów w bazie. Dodaj pierwszy trunek.")

except Exception as e:
    st.error(f"Błąd krytyczny układu logiki: {e}")
