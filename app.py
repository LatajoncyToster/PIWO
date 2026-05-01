import streamlit as st
import pandas as pd
import gspread
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

    # Idioto-odporne czyszczenie liczb (zamiana przecinków na kropki, żeby Python potrafił mnożyć)
    df['Ilość [ml]'] = df['Ilość [ml]'].astype(str).str.replace(',', '.').astype(float)
    df['Moc [%]'] = df['Moc [%]'].astype(str).str.replace(',', '.').astype(float)
    
    # Obliczenia
    df['Czysty etanol [g]'] = df['Ilość [ml]'] * (df['Moc [%]'] / 100) * 0.789
    
    # Mapowanie skrótów
    mapowanie = {'vk': 'Wódka kolorowa', 'p': 'Piwo'}
    df['Alkohol'] = df['Alkohol'].replace(mapowanie)
    
    # Konwersja na prawdziwą datę
    df['Data'] = pd.to_datetime(df['Data'], format='%d.%m.%Y')

    # --- INTERFEJS ---
    st.title("🍺 Alcohol Tracker 3000")
    
    st.subheader("Ostatnie wpisy")
    df_display = df.copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d.%m.%Y')
    st.dataframe(df_display.tail(10))

    st.subheader("Trendy spożycia (Ostatnie 30 dni)")
    
    # Filtrowanie ostatnich 30 dni
    dzisiaj = pd.Timestamp.now()
    miesiac_temu = dzisiaj - pd.Timedelta(days=30)
    df_miesiac = df[df['Data'] >= miesiac_temu]

    if not df_miesiac.empty:
        # Agregacja
        df_chart = df_miesiac.groupby('Data', as_index=False)['Czysty etanol [g]'].sum()
        df_chart['Data_str'] = df_chart['Data'].dt.strftime('%d.%m')
        
        # MAGIA: Zmieniamy nazwę kolumny, żeby usunąć z niej kwadratowe nawiasy!
        df_chart = df_chart.rename(columns={'Czysty etanol [g]': 'Etanol (g)'})
        
        # Rysujemy słupki na bezpiecznej nazwie
        st.bar_chart(data=df_chart, x='Data_str', y='Etanol (g)')
    else:
        st.info("Brak danych z ostatnich 30 dni. Czas coś wpisać!")

except Exception as e:
    st.error(f"Błąd krytyczny: {e}")
