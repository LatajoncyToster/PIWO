import streamlit as st
import pandas as pd
import gspread
import altair as alt
import plotly.express as px  # NOWOŚĆ: Biblioteka do wykresu radarowego
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Alkoholizm jupi", page_icon="🍺", layout="wide")

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

# Konfiguracja autoryzacji GCP
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    sheet = client.open('PIWO').sheet1 
    
    # --- MODUŁ WPROWADZANIA DANYCH (SIDEBAR) ---
    with st.sidebar:
        st.header("📝 Dodaj dane")
        with st.form("add_drink_form", clear_on_submit=True):
            nowa_data = st.date_input("Data spożycia", value=datetime.date.today())
            nowy_alko = st.selectbox("Rodzaj trunku", ["Piwo", "Wódka", "Wódka kolorowa", "Wino", "Inne"])
            nowa_ilosc = st.number_input("Ilość [ml]", min_value=0, step=50, value=500)
            nowa_moc = st.number_input("Moc [%]", min_value=0.0, step=0.5, value=5.0)
            
            submit_button = st.form_submit_button("Dodaj trunek 🍻")
            
            if submit_button:
                reverse_map = {'Wódka kolorowa': 'vk', 'Piwo': 'p', 'Wódka': 'v', 'Wino': 'w', 'Inne': 'i'}
                skrot_alko = reverse_map[nowy_alko]
                data_str = nowa_data.strftime('%d.%m.%Y')
                
                try:
                    sheet.append_row([data_str, skrot_alko, nowa_ilosc, nowa_moc])
                    st.success("Wpis dodany pomyślnie!")
                    st.rerun() 
                except Exception as e:
                    st.error(f"Błąd zapisu do chmury: {e}")
                    
        st.divider()
        st.subheader("⚙️ Szybkie akcje")
        
        # Przyciski zarządzania obok siebie
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("⏪ Cofnij"):
                try:
                    wszystkie_dane = sheet.get_all_values()
                    if len(wszystkie_dane) > 1: 
                        sheet.delete_row(len(wszystkie_dane))
                        st.success("Cofnięto wpis.")
                        st.rerun()
                    else:
                        st.warning("Brak wpisów.")
                except Exception as e:
                    st.error(f"Błąd: {e}")
                    
        with col_btn2:
            if st.button("🔁 Powtórz"):
                try:
                    wszystkie_dane = sheet.get_all_values()
                    if len(wszystkie_dane) > 1:
                        ostatni_rekord = wszystkie_dane[-1]
                        sheet.append_row(ostatni_rekord)
                        st.success("Wjechała ta sama kolejka!")
                        st.rerun()
                    else:
                        st.warning("Najpierw coś wypij.")
                except Exception as e:
                    st.error(f"Błąd: {e}")

    # --- POBIERANIE I CZYSZCZENIE DANYCH ---
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').astype(float)
    df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').astype(float)
    df['Czysty etanol [g]'] = (df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789).round(1)
    
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
    st.title("🍺 Alkoholizm jupi")
    
    ostatni_wpis = df['Data'].max()
    dzisiaj = pd.Timestamp.now().normalize()
    streak = (dzisiaj - ostatni_wpis).days
    if streak < 0: streak = 0 

    if streak == 0:
        st.error(f"🚨 Licznik trzeźwości: {streak} dni. Pite dzisiaj.")
    elif streak == 1:
        st.warning(f"⚠️ Licznik trzeźwości: {streak} dzień. Kac?")
    else:
        st.success(f"🛡️ Licznik trzeźwości: {streak} dni. Wątroba zgłasza proces regeneracji.")

    col_top1, col_top2 = st.columns(2)

    with col_top1:
        st.subheader("Ostatnie wpisy")
        df_display = df.copy()
        skroty_dni = {'Poniedziałek': 'Pon', 'Wtorek': 'Wto', 'Środa': 'Śro', 'Czwartek': 'Czw', 'Piątek': 'Pią', 'Sobota': 'Sob', 'Niedziela': 'Nie'}
        df_display['Dzień'] = df_display['Dzień tygodnia'].map(skroty_dni)
        df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
        kolumny_widoczne = ['Dzień', 'Data', 'Alkohol', 'Ilość [ml]', 'Moc [%]', 'Czysty etanol [g]']
        df_display = df_display[kolumny_widoczne]
        st.dataframe(df_display.tail(10), hide_index=True, use_container_width=True)

    with col_top2:
        # --- GLOBALNY KALENDARZ 365 DNI ---
        st.subheader("📅 Roczna Mapa Zniszczenia (Ostatnie 52 tygodnie)")
        
        rok_temu = dzisiaj - pd.Timedelta(days=365)
        df_365 = df[df['Data'] >= rok_temu]
        
        all_days = pd.date_range(start=rok_temu, end=dzisiaj, freq='D')
        df_heatmap = pd.DataFrame({'Data': all_days})
        
        df_etanol_dziennie = df_365.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
        df_heatmap = df_heatmap.merge(df_etanol_dziennie, on='Data', how='left').fillna(0)
        df_heatmap = df_heatmap.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        
        df_heatmap['Tydzień_Offset'] = ((df_heatmap['Data'] - rok_temu).dt.days // 7).astype(int)
        df_heatmap['Dzień_tygodnia'] = df_heatmap['Data'].dt.dayofweek
        nazwy_krotkie = {0: 'Pon', 1: 'Wto', 2: 'Śro', 3: 'Czw', 4: 'Pią', 5: 'Sob', 6: 'Nie'}
        df_heatmap['Nazwa_dnia'] = df_heatmap['Dzień_tygodnia'].map(nazwy_krotkie)
        
        kolejnosc_kalendarza = ['Pon', 'Wto', 'Śro', 'Czw', 'Pią', 'Sob', 'Nie']
        
        kolorowanie = alt.condition(
            alt.datum['Etanol (g)'] == 0,
            alt.value('#27ae60'), # Zieleń dla trzeźwości
            alt.Color('Etanol (g):Q', scale=alt.Scale(scheme='reds'), legend=alt.Legend(title="Etanol (g)"))
        )

        heatmap = alt.Chart(df_heatmap).mark_rect(stroke='#2d303e', strokeWidth=1, cornerRadius=2).encode(
            x=alt.X('Tydzień_Offset:O', title=None, axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y('Nazwa_dnia:N', sort=kolejnosc_kalendarza, title=None, axis=alt.Axis(labelPadding=5)), 
            color=kolorowanie,
            tooltip=['Data', 'Etanol (g)']
        ).properties(height=200)

        st.altair_chart(heatmap, use_container_width=True)

    st.divider()

    # --- PANEL OPERACYJNY 30-DNIOWY ---
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
        
        st.markdown("**Twój urobek z ostatnich 30 dni w przeliczeniu na:**")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(label="🍺 Kufle piwa (5%)", value=eq_kufle, delta=delta_kufle, delta_color="inverse")
        kpi2.metric(label="🥃 Shoty wódki (40ml)", value=eq_shoty, delta=delta_shoty, delta_color="inverse")
        kpi3.metric(label="🍾 Flaszki 0.7 (40%)", value=eq_flaszki, delta=delta_flaszki, delta_color="inverse")
        
        st.divider() 
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("**Trendy spożycia i uśredniony ciąg**")
            df_chart = df_miesiac.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
            min_date = df_chart['Data'].min()
            full_date_range = pd.date_range(start=min_date, end=dzisiaj, freq='D')
            df_chart = df_chart.set_index('Data').reindex(full_date_range, fill_value=0).reset_index()
            
            df_chart = df_chart.rename(columns={'index': 'Data', 'Czysty etanol [g]': 'Etanol (g)'})
            df_chart['Data_str'] = df_chart['Data'].dt.strftime('%d.%m')
            df_chart['Trend (3-dniowy)'] = df_chart['Etanol (g)'].rolling(window=3, min_periods=1).mean()

            base = alt.Chart(df_chart).encode(x=alt.X('Data_str:N', sort=None, title='Data'))
            bars = base.mark_bar(color='#85c1e9').encode(y=alt.Y('Etanol (g):Q', title='Spożycie (g)'))
            line = base.mark_line(color='#e74c3c', size=3).encode(y='Trend (3-dniowy):Q')
            st.altair_chart(bars + line, use_container_width=True)
            
        with col2:
            st.markdown("**Radar Preferencji (Spider Chart)**")
            
            # Nowy, profesjonalny wykres radarowy z biblioteki Plotly
            df_radar = df_miesiac.rename(columns={'Czysty etanol [g]': 'Etanol (g)'}).groupby('Alkohol')['Etanol (g)'].sum().reset_index()
            fig = px.line_polar(df_radar, r='Etanol (g)', theta='Alkohol', line_close=True, template="plotly_dark", color_discrete_sequence=['#e74c3c'])
            fig.update_traces(fill='toself', fillcolor='rgba(231, 76, 60, 0.5)')
            fig.update_layout(margin=dict(t=30, b=30, l=30, r=30))
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Brak danych z ostatnich 30 dni w rejestrze.")

    st.divider()

    # --- ANALITYKA HISTORYCZNA ---
    st.subheader("Analiza Historyczna")
    
    tab1, tab2, tab3 = st.tabs(["📅 Struktura Dni Tygodnia", "📈 Podsumowanie Miesięcy", "🏆 Hall of Shame (Top 3)"])
    
    with tab1:
        st.markdown("**Całkowita struktura urobku w dany dzień tygodnia z podziałem na trunki**")
        df_dni = df.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        
        # Agregacja do wykresu warstwowego (Stacked Bar)
        df_dni_stacked = df_dni.groupby(['Dzień tygodnia', 'Alkohol'])['Etanol (g)'].sum().reset_index()
        
        # Nowa, customowa paleta kolorów wg wytycznych
        kolory_alko = alt.Scale(
            domain=['Piwo', 'Wódka kolorowa', 'Wódka', 'Wino', 'Inne'],
            range=['#f1c40f', '#e84393', '#ffffff', '#e74c3c', '#95a5a6']
        )
        
        bar_dni = alt.Chart(df_dni_stacked).mark_bar().encode(
            x=alt.X('Dzień tygodnia:N', sort=kolejnosc_dni, title='Dzień tygodnia'),
            y=alt.Y('Etanol (g):Q', title='Całkowity urobek etanolu (g)'),
            color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(title="Trunek")),
            tooltip=['Dzień tygodnia', 'Alkohol', 'Etanol (g)']
        ).properties(height=300)
        
        st.altair_chart(bar_dni, use_container_width=True)

    with tab2:
        st.markdown("**Ile ŚREDNIO wlewam w siebie w dany miesiąc**")
        df_miesiace = df.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        df_miesiace = df_miesiace[df_miesiace['Miesiąc'] != 'Kwiecień']
        df_miesiace = df_miesiace.groupby('Miesiąc')['Etanol (g)'].mean().round(1).reset_index()
        
        bar_miesiace = alt.Chart(df_miesiace).mark_bar(color='#f39c12').encode(
            x=alt.X('Miesiąc:N', sort=kolejnosc_miesiecy, title='Miesiąc'),
            y=alt.Y('Etanol (g):Q', title='Średnio etanolu (g) / posiedzenie'),
            tooltip=['Miesiąc', 'Etanol (g)']
        ).properties(height=300)
        st.altair_chart(bar_miesiace, use_container_width=True)

    with tab3:
        st.markdown("**Dni największego woltażu:**")
        df_podium = df.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
        df_podium = df_podium.sort_values(by='Czysty etanol [g]', ascending=False).head(3).reset_index(drop=True)
        
        if not df_podium.empty:
            medale = ["🥇", "🥈", "🥉"]
            for i, row in df_podium.iterrows():
                data_format = row['Data'].strftime('%d.%m.%Y')
                gramy = row['Czysty etanol [g]']
                eq_kufle_podium = int(round(gramy / 19.725, 0)) 
                
                st.markdown(f"### {medale[i]} **{data_format}**")
                st.markdown(f"**Etanol:** {gramy}g *(Równowartość ok. {eq_kufle_podium} piw jednego dnia!)*")
                st.divider()

except Exception as e:
    st.error(f"Błąd krytyczny układu logiki: {e}")
