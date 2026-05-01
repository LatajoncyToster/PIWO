import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Konfiguracja autoryzacji
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

    # Transformacja danych
    mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo'}
    df['Alkohol'] = df['Alkohol'].replace(mapowanie)
    
    # Czyszczenie i kalkulacje
    df['Ilość [ml]'] = pd.to_numeric(df['Ilość [ml]'], errors='coerce')
    df['Moc [%]'] = pd.to_numeric(df['Moc [%]'], errors='coerce')
    df['Czysty etanol [g]'] = df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789

    # Konwersja na prawdziwą datę
    df['Data'] = pd.to_datetime(df['Data'], format='%d.%m.%Y')

    # --- INTERFEJS ---
    st.title("🍺 Alcohol Tracker 3000")
    
    st.subheader("Ostatnie wpisy")
    df_display = df.copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
    st.dataframe(df_display.tail(10))

    st.subheader("Trendy spożycia (Ostatnie 30 dni)")
    
    # Filtracja z ostatnich 30 dni
    dzisiaj = pd.Timestamp.now()
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    df_miesiac = df[df['Data'] >= miesiac_temu]

    if not df_miesiac.empty:
        # PANCERNY WYKRES: as_index=False ratuje oś X przed zniknięciem
        df_chart = df_miesiac.groupby('Data', as_index=False)['Czysty etanol [g]'].sum()
        
        # Konwersja daty na tekst w formacie YYYY-MM-DD, żeby wykres był czysty
        df_chart['Data'] = df_chart['Data'].dt.strftime('%Y-%m-%d')
        
        # Rysujemy słupki, wyraźnie deklarując co jest czym
        st.bar_chart(data=df_chart, x='Data', y='Czysty etanol [g]')
    else:
        st.info("Brak danych z ostatnich 30 dni. Jesteś trzeźwy, czy zapomniałeś wpisać?")

except Exception as e:
    st.error(f"Błąd krytyczny: {e}")
