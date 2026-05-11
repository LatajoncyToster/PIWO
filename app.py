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
            
            submit_button = st.form_submit_button("Dodaj trunek")
            
            if submit_button:
                reverse_map = {'Wódka kolorowa': 'vk', 'Piwo': 'p', 'Wódka': 'v', 'Wino': 'w', 'Inne': 'i'}
                skrot_alko = reverse_map[nowy_alko]
                data_str = nowa_data.strftime('%d.%m.%Y')
                strefa_pl = ZoneInfo('Europe/Warsaw')
                nowy_czas = datetime.datetime.now(strefa_pl).strftime('%H:%M') 
                
                try:
                    sheet.append_row([data_str, skrot_alko, float(nowa_ilosc), float(nowa_moc), nowy_czas], value_input_option='RAW')
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
        
        if 'Godz.' not in df.columns: df['Godz.'] = '--:--'
        else: df['Godz.'] = df['Godz.'].fillna('--:--').replace('', '--:--').astype(str)
        
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
        
        if streak == 0: st.error(f"Licznik trzeźwości: {streak} dni")
        elif streak == 1: st.warning(f"Licznik trzeźwości: {streak} dzień")
        else: st.success(f"Licznik trzeźwości: {streak} dni")

        col_top1, col_top2 = st.columns(2)

        with col_top1:
            st.subheader("Ostatnie wpisy")
            df_disp = df.copy()
            df_disp['Data_str'] = df_disp['Data'].dt.strftime('%d.%m.%Y')
            df_final = df_disp[['Dzień tygodnia', 'Data_str', 'Godz.', 'Alkohol', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']].iloc[::-1].copy()
            df_final.columns = ['Dzień tygodnia', 'Data', 'Godz.', 'Alkohol', 'Ilość [ml]', 'Moc [%]', 'Etanol [g]']
            
            def highlight_dates(data):
                mask = data['Data'].factorize()[0] % 2 == 0
                return pd.DataFrame([['background-color: rgba(255, 255, 255, 0.08)' if m else '' for _ in data.columns] for m in mask], index=data.index, columns=data.columns)
                
            st.dataframe(df_final.style.apply(highlight_dates, axis=None).format({'Ilość [ml]': '{:.0f}', 'Moc [%]': '{:.1f}', 'Etanol [g]': '{:.1f}'}), hide_index=True, use_container_width=True, height=350)

        with col_top2:
            st.subheader("Kalendarz (Miesięczny)")
            if 'kalendarz_offset' not in st.session_state: st.session_state.kalendarz_offset = 0
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1: 
                if st.button("Poprzedni"): st.session_state.kalendarz_offset -= 1
            with c3:
                if st.button("Następny"): st.session_state.kalendarz_offset += 1
            aktywna = dzisiaj + pd.DateOffset(months=st.session_state.kalendarz_offset)
            with c2: st.markdown(f"<h4 style='text-align: center;'>{aktywna.strftime('%m.%Y')}</h4>", unsafe_allow_html=True)
            
            dni_m = pd.date_range(start=aktywna.replace(day=1), end=(aktywna.replace(day=1) + pd.DateOffset(months=1)) - pd.Timedelta(days=1), freq='D')
            df_k = pd.DataFrame({'Data': dni_m}).merge(df.groupby('Data')['Czysty etanol [g]'].sum().reset_index(), on='Data', how='left').fillna(0)
            df_k['Nazwa'] = df_k['Data'].dt.dayofweek.map({0: 'Pon', 1: 'Wto', 2: 'Śro', 3: 'Czw', 4: 'Pią', 5: 'Sob', 6: 'Nie'})
            df_k['Dzien'] = df_k['Data'].dt.day.astype(str)
            df_k['Rzad'] = df_k['Data'].apply(lambda d: (d.day - 1 + d.replace(day=1).weekday()) // 7)
            
            heatmap = alt.Chart(df_k).mark_rect(stroke='gray', strokeWidth=0.5, cornerRadius=3).encode(
                x=alt.X('Nazwa:N', sort=['Pon','Wto','Śro','Czw','Pią','Sob','Nie'], title=None),
                y=alt.Y('Rzad:O', title=None, axis=alt.Axis(labels=False, ticks=False)), 
                color=alt.condition(alt.datum['Czysty etanol [g]'] == 0, alt.value('#27ae60'), alt.Color('Czysty etanol [g]:Q', scale=alt.Scale(scheme='reds'))),
                tooltip=[alt.Tooltip('Data:T', format='%d.%m.%Y'), 'Czysty etanol [g]']
            ).properties(height=250)
            st.altair_chart(heatmap + alt.Chart(df_k).mark_text(baseline='middle').encode(x='Nazwa:N', y='Rzad:O', text='Dzien', color=alt.condition(alt.datum['Czysty etanol [g]'] > 60, alt.value('white'), alt.value('black'))), use_container_width=True)

        st.subheader("Tygodnie")
        niedziela = dzisiaj + pd.Timedelta(days=(6 - dzisiaj.dayofweek))
        df_52 = df[df['Data'] >= niedziela - pd.Timedelta(days=364)].copy()
        df_t = pd.DataFrame({'Off': range(51, -1, -1)})
        df_t['Kon'] = niedziela - pd.to_timedelta(df_t['Off'] * 7, unit='D')
        df_t['Poc'] = df_t['Kon'] - pd.Timedelta(days=6)
        if not df_52.empty:
            df_52['Off'] = ((niedziela - df_52['Data']).dt.days // 7)
            df_t = pd.merge(df_t, df_52.groupby('Off')['Czysty etanol [g]'].sum().reset_index(), on='Off', how='left').fillna(0)
        else: df_t['Czysty etanol [g]'] = 0
        st.altair_chart(alt.Chart(df_t).mark_rect(stroke='#2d303e', strokeWidth=1, cornerRadius=2).encode(
            x=alt.X('Off:O', sort='descending', axis=alt.Axis(labels=False, ticks=False), title='Starsze -> Nowsze'),
            y=alt.Y('Off:O', axis=alt.Axis(labels=False, ticks=False), title=None),
            color=alt.condition(alt.datum['Czysty etanol [g]'] == 0, alt.value('#27ae60'), alt.Color('Czysty etanol [g]:Q', scale=alt.Scale(scheme='reds'))),
            tooltip=['Czysty etanol [g]']
        ).properties(height=80), use_container_width=True)

        st.divider()
        st.subheader("Panel (30 dni)")
        df_m = df[df['Data'] >= dzisiaj - pd.Timedelta(days=30)]
        if not df_m.empty:
            et = df_m['Czysty etanol [g]'].sum()
            # Przelicznik na litry wódki 40% (1L = 315.6g etanolu)
            kp1, kp2, kp3 = st.columns(3)
            kp1.metric("Puszki piwa (5%)", int(round(et / 19.725, 0)))
            kp2.metric("Shoty wódki (40ml)", int(round(et / 12.624, 0)))
            kp3.metric("Litry wódki (40%)", round(et / 315.6, 2))
            
            c1, c2 = st.columns([2, 1])
            with c1:
                df_c = df_m.groupby(['Data', 'Alkohol'])['Czysty etanol [g]'].sum().reset_index().rename(columns={'Czysty etanol [g]': 'g'})
                st.altair_chart(alt.Chart(df_c).mark_bar(size=15).encode(x=alt.X('yearmonthdate(Data):O', axis=alt.Axis(format='%d.%m', labelAngle=-90)), y='g:Q', color=alt.Color('Alkohol:N', scale=alt.Scale(domain=['Piwo','Wódka kolorowa','Wódka','Wino','Inne'], range=['#f1c40f','#e84393','#ffffff','#e74c3c','#95a5a6']))), use_container_width=True)
            with c2:
                st.altair_chart(alt.Chart(df_m.groupby('Alkohol')['Czysty etanol [g]'].sum().reset_index()).mark_arc(innerRadius=50).encode(theta='Czysty etanol [g]:Q', color='Alkohol:N'), use_container_width=True)
        
        st.divider()
        st.subheader("Analiza Historyczna")
        tab1, tab2, tab3, tab4 = st.tabs(["Tydzień", "Miesiące", "Top 3: Spożycie", "Top 3: Przerwy"])
        with tab1: st.altair_chart(alt.Chart(df.groupby('Dzień tygodnia')['Czysty etanol [g]'].mean().reset_index()).mark_bar(color='#9b59b6').encode(x=alt.X('Dzień tygodnia:N', sort=kolejnosc_dni), y='Czysty etanol [g]:Q'), use_container_width=True)
        with tab2: st.altair_chart(alt.Chart(df[df['Miesiąc'] != 'Kwiecień'].groupby('Miesiąc')['Czysty etanol [g]'].mean().reset_index()).mark_bar(color='#f39c12').encode(x=alt.X('Miesiąc:N', sort=kolejnosc_miesiecy), y='Czysty etanol [g]:Q'), use_container_width=True)
        
        with tab3:
            df_p = df.groupby(['Data', 'Dzień tygodnia'])['Czysty etanol [g]'].sum().reset_index().sort_values(by='Czysty etanol [g]', ascending=False).head(3)
            # Kompaktowy widok Top 3 bez emotikon i z litrami
            for i, (_, r) in enumerate(df_p.iterrows()):
                g = round(r['Czysty etanol [g]'], 1)
                st.write(f"**{i+1}. {r['Data'].strftime('%d.%m.%Y')} ({r['Dzień tygodnia']})**")
                st.write(f"Etanol: {g}g | {int(round(g/19.725, 0))} puszki | {int(round(g/12.624, 0))} shoty | {round(g/315.6, 2)}l wódki")
                st.write("---")

        with tab4:
            u_d = df['Data'].dt.normalize().drop_duplicates().sort_values().reset_index(drop=True)
            gaps = []
            for i in range(1, len(u_d)):
                d = (u_d[i] - u_d[i-1]).days - 1
                if d > 0: gaps.append({'d': d, 'ok': f"{u_d[i-1].strftime('%d.%m')} - {u_d[i].strftime('%d.%m')}"})
            for i, g in enumerate(sorted(gaps, key=lambda x: x['d'], reverse=True)[:3]):
                st.write(f"**{i+1}. {g['d']} dni** ({g['ok']})")
                st.write("---")
    else: st.warning("Brak danych.")
except Exception as e: st.error(f"Błąd krytyczny: {e}")
