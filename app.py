import streamlit as st
import pandas as pd
import gspread
import altair as alt
from oauth2client.service_account import ServiceAccountCredentials
import datetime

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
            nowy_alko = st.selectbox("Rodzaj trunku", ["Piwo", "Wódka", "Wódka kolorowa", "Inne"])
            nowa_ilosc = st.number_input("Ilość [ml]", min_value=0, step=50, value=500)
            nowa_moc = st.number_input("Moc [%]", min_value=0.0, step=0.5, value=5.0)
            
            submit_button = st.form_submit_button("Dodaj napitek 🍻")
            
            if submit_button:
                # Słownik mapowania odwrotnego (do zapisu skrótów w arkuszu)
                reverse_map = {'Wódka kolorowa': 'vk', 'Piwo': 'p', 'Wódka': 'v', 'Inne': 'i'}
                skrot_alko = reverse_map[nowy_alko]
                data_str = nowa_data.strftime('%d.%m.%Y')
                
                try:
                    # Dodanie nowego wiersza na końcu arkusza
                    sheet.append_row([data_str, skrot_alko, nowa_ilosc, nowa_moc])
                    st.success("Wpis dodany pomyślnie!")
                    st.rerun() # Wymuszenie twardego przeładowania aplikacji
                except Exception as e:
                    st.error(f"Błąd zapisu do chmury: {e}")

    # --- POBIERANIE I CZYSZCZENIE DANYCH ---
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').astype(float)
    df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').astype(float)
    
    df['Czysty etanol [g]'] = (df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789).round(1)
    
    mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo', 'v': 'Wódka', 'i': 'Inne'}
    df['Alkohol'] = df['Alkohol'].replace(mapowanie)
    
    df['Data'] = pd.to_datetime(df['Data'], format='%d.%m.%Y')

    # --- INTERFEJS GŁÓWNY ---
    st.title("🍺 Alcohol Tracker 3000")
    
    ostatni_wpis = df['Data'].max()
    dzisiaj = pd.Timestamp.now().normalize()
    streak = (dzisiaj - ostatni_wpis).days
    
    if streak < 0: 
        streak = 0 

    if streak == 0:
        st.error(f"🚨 Licznik trzeźwości: {streak} dni. Pite dzisiaj.")
    elif streak == 1:
        st.warning(f"⚠️ Licznik trzeźwości: {streak} dzień. Kac?")
    else:
        st.success(f"🛡️ Licznik trzeźwości: {streak} dni. Wątroba zgłasza proces regeneracji.")

    st.subheader("Ostatnie wpisy")
    df_display = df.copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
    st.dataframe(df_display.tail(10))

    st.subheader("Panel Analityczny (Ostatnie 30 dni)")
    
    dzisiaj_okres = pd.Timestamp.now().normalize()
    miesiac_temu = dzisiaj_okres - pd.Timedelta(days=30)
    df_miesiac = df[df['Data'] >= miesiac_temu]

    if not df_miesiac.empty:
        
        total_etanol = df_miesiac['Czysty etanol [g]'].sum()
        
        eq_kufle = int(round(total_etanol / 19.725, 0))  
        eq_shoty = int(round(total_etanol / 12.624, 0))  
        eq_flaszki = round(total_etanol / 220.92, 1)     
        
        st.markdown("**Twój urobek z ostatnich 30 dni w przeliczeniu na:**")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(label="🍺 Kufle piwa (5%)", value=eq_kufle)
        kpi2.metric(label="🥃 Shoty wódki (40ml)", value=eq_shoty)
        kpi3.metric(label="🍾 Flaszki 0.7 (40%)", value=eq_flaszki)
        
        st.divider() 
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("**Trend spożycia**")
            
            df_chart = df_miesiac.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
            min_date = df_chart['Data'].min()
            full_date_range = pd.date_range(start=min_date, end=dzisiaj_okres, freq='D')
            df_chart = df_chart.set_index('Data').reindex(full_date_range, fill_value=0).reset_index()
            
            df_chart = df_chart.rename(columns={'index': 'Data', 'Czysty etanol [g]': 'Etanol (g)'})
            df_chart['Data_str'] = df_chart['Data'].dt.strftime('%d.%m')
            
            df_chart['Trend (3-dniowy)'] = df_chart['Etanol (g)'].rolling(window=3, min_periods=1).mean()

            base = alt.Chart(df_chart).encode(x=alt.X('Data_str:N', sort=None, title='Data'))
            bars = base.mark_bar(color='#85c1e9').encode(y=alt.Y('Etanol (g):Q', title='Spożycie (g)'))
            line = base.mark_line(color='#e74c3c', size=3).encode(y='Trend (3-dniowy):Q')

            st.altair_chart(bars + line, use_container_width=True)
            
        with col2:
            st.markdown("**Struktura spożycia**")
            
            df_donut = df_miesiac.copy()
            df_donut = df_donut.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
            df_donut = df_donut.groupby('Alkohol')['Etanol (g)'].sum().reset_index()
            
            donut = alt.Chart(df_donut).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Etanol (g)", type="quantitative"),
                color=alt.Color(field="Alkohol", type="nominal", legend=alt.Legend(title="Trunek")),
                tooltip=['Alkohol', alt.Tooltip('Etanol (g)', format='.1f')]
            ).properties(height=350)
            
            st.altair_chart(donut, use_container_width=True)

    else:
        st.info("Brak danych z ostatnich 30 dni w rejestrze.")

except Exception as e:
    st.error(f"Błąd krytyczny układu logiki: {e}")
