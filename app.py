import streamlit as st
import pandas as pd
import gspread
import altair as alt
from oauth2client.service_account import ServiceAccountCredentials

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    sheet = client.open('PIWO').sheet1 
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # Czyszczenie struktur liczbowych
    df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').astype(float)
    df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').astype(float)
    
    # Obliczenia fizykochemiczne
    df['Czysty etanol [g]'] = df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789
    
    # Mapowanie skrótów 
    mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo'}
    df['Alkohol'] = df['Alkohol'].replace(mapowanie)
    
    # Normalizacja wektorów czasowych
    df['Data'] = pd.to_datetime(df['Data'], format='%d.%m.%Y')

    # --- INTERFEJS ---
    st.title("🍺 Alcohol Tracker 3000")
    
    st.subheader("Ostatnie wpisy")
    df_display = df.copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
    st.dataframe(df_display.tail(10))

    st.subheader("Trendy spożycia (Ostatnie 30 dni)")
    
    # Definicja horyzontu czasowego
    dzisiaj = pd.Timestamp.now()
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    df_miesiac = df[df['Data'] >= miesiac_temu]

    if not df_miesiac.empty:
        # Agregacja i normalizacja atrybutów wykresu
        df_chart = df_miesiac.groupby('Data', as_index=False)['Czysty etanol [g]'].sum()
        df_chart = df_chart.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        df_chart['Data_str'] = df_chart['Data'].dt.strftime('%d.%m')
        
        # Obliczenie linii trendu z wykorzystaniem 3-dniowej średniej kroczącej
        df_chart['Trend (3-dniowy)'] = df_chart['Etanol (g)'].rolling(window=3, min_periods=1).mean()

        # Generowanie obieków wizualizacyjnych w przestrzeni Altair
        base = alt.Chart(df_chart).encode(
            x=alt.X('Data_str:N', sort=None, title='Data')
        )
        
        # Słupki bazowe
        bars = base.mark_bar(color='#85c1e9').encode(
            y=alt.Y('Etanol (g):Q', title='Spożycie (g) / Trend')
        )
        
        # Nakładka linii trendu
        line = base.mark_line(color='#e74c3c', size=3).encode(
            y='Trend (3-dniowy):Q'
        )

        # Renderowanie finalnej kompozycji
        st.altair_chart(bars + line, use_container_width=True)
    else:
        st.info("Brak danych z ostatnich 30 dni. Czas coś wpisać!")

except Exception as e:
    st.error(f"Błąd krytyczny procedury: {e}")
