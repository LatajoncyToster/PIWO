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

    # Transformacja danych i mapowanie skrótów
    mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo'}
    df['Alkohol'] = df['Alkohol'].replace(mapowanie)
    
    # Wymuszenie typów liczbowych na wypadek, gdyby Google Sheets wypluł tekst
    df['Ilość [ml]'] = pd.to_numeric(df['Ilość [ml]'], errors='coerce')
    df['Moc [%]'] = pd.to_numeric(df['Moc [%]'], errors='coerce')
    
    # Obliczanie masy czystego etanolu
    df['Czysty etanol [g]'] = df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789

    # Konwersja tekstu na obiekt daty
    df['Data'] = pd.to_datetime(df['Data'], format='%d.%m.%Y')

    # Interfejs
    st.title("🍺 Alcohol Tracker 3000")
    
    st.subheader("Ostatnie wpisy")
    # Zamieniamy datę z powrotem na ładny tekst tylko do wyświetlenia w tabeli
    df_display = df.copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
    st.dataframe(df_display.tail(10))

    st.subheader("Trendy spożycia (Ostatnie 30 dni)")
    
    # Filtracja danych z ostatniego miesiąca
    dzisiaj = pd.Timestamp.now()
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    df_miesiac = df[df['Data'] >= miesiac_temu]

    # Agregacja i przygotowanie wykresu
    if not df_miesiac.empty:
        # Sumujemy etanol dla każdego dnia (jak wypijesz 3 piwa jednego dnia, zsumuje je)
        df_chart = df_miesiac.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
        df_chart = df_chart.set_index('Data')
        
        # Wymuszamy, żeby Streamlit przyjął to jako pełnoprawną ramkę danych
        # i rysujemy potężne słupki (bar_chart)
        st.bar_chart(df_chart[['Czysty etanol [g]']])
    else:
        st.info("Brak danych z ostatnich 30 dni. Jesteś trzeźwy, czy zapomniałeś wpisać?")

except Exception as e:
    st.error(f"Błąd krytyczny: {e}")
