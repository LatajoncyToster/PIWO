import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Konfiguracja autoryzacji przez Streamlit Secrets (dla bezpieczeństwa w chmurze)
def get_gspread_client():
    # Dane autoryzacyjne będą pobierane z bezpiecznych ustawień Streamlit Cloud
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

try:
    client = get_gspread_client()
    # WPISZ PONIŻEJ DOKŁADNĄ NAZWĘ SWOJEGO ARKUSZA
    sheet = client.open('PIWO').sheet1 
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    # Logika transformacji danych
    # Mapujemy Twoje skróty na pełne nazwy dla estetyki wykresów
    mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo','v': 'Wódka'}
    df['Alkohol'] = df['Alkohol'].replace(mapowanie)

    # Obliczanie czystego etanolu (Skasowałeś kolumnę w Excelu, więc liczymy tutaj)
    df['Czysty etanol [g]'] = df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789

    # Interfejs Streamlit
    st.title("Alcohol Tracker 3000")
    
    st.subheader("Ostatnie wpisy")
    st.write(df.tail(10))

    st.subheader("Spożycie czystego etanolu w czasie")
    # Agregacja po dacie, żeby wykres był czytelny
    df_chart = df.groupby('Data')['Czysty etanol [g]'].sum().reset_index()
    st.line_chart(data=df_chart, x='Data', y='Czysty etanol [g]')

except Exception as e:
    st.error(f"Coś wywaliło: {e}")
    st.info("Upewnij się, że nazwa arkusza w kodzie jest identyczna z tą w Google Sheets.")