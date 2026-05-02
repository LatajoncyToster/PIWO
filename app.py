import streamlit as st
import pandas as pd
import gspread
import altair as alt
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Alkoholizm", page_icon="🍺", layout="wide")

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
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("⏪ Cofnij ostatni wpis"):
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
    st.title("🍺 Alkoholizm")
    
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
        st.subheader("📅 Kalendarz Spożycia (Miesięczny)")
        
        if 'kalendarz_offset' not in st.session_state:
            st.session_state.kalendarz_offset = 0

        col_btn_l, col_miesiac, col_btn_r = st.columns([1, 2, 1])
        
        with col_btn_l:
            if st.button("⬅️ Poprzedni"):
                st.session_state.kalendarz_offset -= 1
                
        with col_btn_r:
            if st.button("Następny ➡️"):
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
            alt.Color('Etanol (g):Q', scale=alt.Scale(scheme='reds'), legend=alt.Legend(title="Etanol (g)"))
        )

        heatmap = alt.Chart(df_kalendarz).mark_rect(stroke='gray', strokeWidth=0.5, cornerRadius=3).encode(
            x=alt.X('Nazwa_dnia:N', sort=kolejnosc_kalendarza, title=None, axis=alt.Axis(labelAngle=0, labelPadding=10)),
            y=alt.Y('Rząd_tygodnia:O', title=None, axis=alt.Axis(labels=False, ticks=False)), 
            color=kolorowanie,
            tooltip=['Data', 'Etanol (g)']
        ).properties(height=250)
        
        text = alt.Chart(df_kalendarz).mark_text(baseline='middle').encode(
            x=alt.X('Nazwa_dnia:N', sort=kolejnosc_kalendarza),
            y=alt.Y('Rząd_tygodnia:O'),
            text=alt.Text('Dzień_miesiąca:N'),
            color=alt.condition(alt.datum['Etanol (g)'] > 60, alt.value('white'), alt.value('black'))
        )

        st.altair_chart(heatmap + text, use_container_width=True)

    # --- PANCERNA ROCZNA MAPA ZNISZCZENIA (MATEMATYCZNA) ---
    st.subheader("🗓️ Roczna Mapa Zniszczenia (Tygodnie od lewej do prawej)")
    
    rok_temu_tydzien = dzisiaj - pd.Timedelta(days=364)
    df_52 = df[df['Data'] >= rok_temu_tydzien].copy()
    
    # Tworzymy sztywny szkielet dla 52 tygodni (od 51 do 0, gdzie 0 to obecny tydzień)
    df_tygodnie = pd.DataFrame({'Tydzień_Offset': range(51, -1, -1)})
    
    if not df_52.empty:
        # Obliczamy matematycznie ile tygodni temu był dany wpis
        df_52['Tydzień_Offset'] = ((dzisiaj - df_52['Data']).dt.days // 7)
        # Bierzemy pod uwagę tylko wpisy łapiące się w 52 oknach
        df_52 = df_52[df_52['Tydzień_Offset'] <= 51]
        
        weekly_sum = df_52.groupby('Tydzień_Offset')['Czysty etanol [g]'].sum().reset_index()
        df_heatmap_tyg = pd.merge(df_tygodnie, weekly_sum, on='Tydzień_Offset', how='left').fillna(0)
    else:
        df_heatmap_tyg = df_tygodnie.copy()
        df_heatmap_tyg['Czysty etanol [g]'] = 0

    # Tworzymy ostateczną numerację od lewej do prawej (od 1 do 52)
    df_heatmap_tyg['Tydzień_Num'] = range(1, 53)
    df_heatmap_tyg['Wiersz'] = 'Postęp w roku'
    df_heatmap_tyg = df_heatmap_tyg.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
    
    kolorowanie_tygodni = alt.condition(
        alt.datum['Etanol (g)'] == 0,
        alt.value('#27ae60'), # Zieleń dla czystego tygodnia
        alt.Color('Etanol (g):Q', scale=alt.Scale(scheme='reds'), legend=alt.Legend(title="Etanol (g/tydz)"))
    )

    heatmap_tygodniowa = alt.Chart(df_heatmap_tyg).mark_rect(stroke='#2d303e', strokeWidth=1, cornerRadius=2).encode(
        x=alt.X('Tydzień_Num:O', title='Kolejne tygodnie w roku (Od najstarszego do teraz)', axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y('Wiersz:N', title=None, axis=alt.Axis(labels=False, ticks=False)), 
        color=kolorowanie_tygodni,
        tooltip=['Etanol (g)']
    ).properties(height=80)

    st.altair_chart(heatmap_tygodniowa, use_container_width=True)

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
        
        # Mapa kolorów dla trunków w trendach
        kolory_alko = alt.Scale(
            domain=['Piwo', 'Wódka kolorowa', 'Wódka', 'Wino', 'Inne'],
            range=['#f1c40f', '#e84393', '#ffffff', '#e74c3c', '#95a5a6']
        )
        
        with col1:
            st.markdown("**Trendy spożycia i uśredniony ciąg (z podziałem na kolory trunków)**")
            
            df_chart_bars = df_miesiac.groupby(['Data', 'Alkohol'])['Czysty etanol [g]'].sum().reset_index()
            df_chart_bars['Data_str'] = df_chart_bars['Data'].dt.strftime('%d.%m')
            df_chart_bars = df_chart_bars.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
            
            df_chart_line = df_miesiac.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
            min_date = df_chart_line['Data'].min()
            full_date_range = pd.date_range(start=min_date, end=dzisiaj, freq='D')
            df_chart_line = df_chart_line.set_index('Data').reindex(full_date_range, fill_value=0).reset_index()
            df_chart_line['index_str'] = df_chart_line['index'].dt.strftime('%d.%m')
            df_chart_line['Trend (3-dniowy)'] = df_chart_line['Czysty etanol [g]'].rolling(window=3, min_periods=1).mean()

            base_bars = alt.Chart(df_chart_bars).mark_bar().encode(
                x=alt.X('Data_str:N', sort=None, title='Data'),
                y=alt.Y('Etanol (g):Q', title='Spożycie (g)'),
                color=alt.Color('Alkohol:N', scale=kolory_alko, legend=alt.Legend(title="Trunek")),
                tooltip=['Data_str', 'Alkohol', 'Etanol (g)']
            )
            
            base_line = alt.Chart(df_chart_line).mark_line(color='#3498db', size=3).encode(
                x=alt.X('index_str:N', sort=None),
                y=alt.Y('Trend (3-dniowy):Q')
            )
            
            st.altair_chart(base_bars + base_line, use_container_width=True)
            
        with col2:
            st.markdown("**Struktura spożycia**")
            df_donut = df_miesiac.rename(columns={'Czysty etanol [g]': 'Etanol (g)'}).groupby('Alkohol')['Etanol (g)'].sum().reset_index()
            
            donut = alt.Chart(df_donut).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Etanol (g)", type="quantitative"),
                color=alt.Color(field="Alkohol", type="nominal", scale=kolory_alko, legend=alt.Legend(title="Trunek")),
                tooltip=['Alkohol', alt.Tooltip('Etanol (g)', format='.1f')]
            ).properties(height=350)
            
            st.altair_chart(donut, use_container_width=True)
    else:
        st.info("Brak danych z ostatnich 30 dni w rejestrze.")

    st.divider()

    # --- ANALITYKA HISTORYCZNA ---
    st.subheader("Analiza Historyczna")
    
    tab1, tab2, tab3 = st.tabs(["📅 Rozkład Tygodniowy", "📈 Podsumowanie Miesięcy", "🏆 Hall of Shame (Top 3)"])
    
    with tab1:
        st.markdown("**Ile ŚREDNIO wlewam w siebie w dany dzień tygodnia?**")
        df_dni = df.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        df_dni = df_dni.groupby('Dzień tygodnia')['Etanol (g)'].mean().round(1).reset_index()
        
        # Zwykły fioletowy kolor
        bar_dni = alt.Chart(df_dni).mark_bar(color='#9b59b6').encode(
            x=alt.X('Dzień tygodnia:N', sort=kolejnosc_dni, title='Dzień tygodnia'),
            y=alt.Y('Etanol (g):Q', title='Średnio etanolu (g) / posiedzenie'),
            tooltip=['Dzień tygodnia', 'Etanol (g)']
        ).properties(height=300)
        st.altair_chart(bar_dni, use_container_width=True)

    with tab2:
        st.markdown("**Ile ŚREDNIO wlewam w siebie w dany miesiąc**")
        df_miesiace = df.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        df_miesiace = df_miesiace[df_miesiace['Miesiąc'] != 'Kwiecień']
        df_miesiace = df_miesiace.groupby('Miesiąc')['Etanol (g)'].mean().round(1).reset_index()
        
        # Zwykły pomarańczowy kolor
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
