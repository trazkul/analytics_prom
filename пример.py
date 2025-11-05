import os
import logging
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from selenium.common.exceptions import WebDriverException

# Настройка логирования
logging.basicConfig(
    filename="scraper_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# Функция для отправки сообщения в Telegram
def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            logging.error(f"Не удалось отправить сообщение в Telegram: {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения в Telegram: {e}")


# Telegram Bot токен и chat_id
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Google Sheets настройки
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

# Настройка Selenium
chrome_options = Options()
chrome_options.add_argument("--incognito")
chrome_options.add_argument("--headless")

# Запросы для поиска
queries = [
    "Аквадистиллятор",
    "Банкетка медицинская",
    "Камера ультрафиолетовая",
    "Кресло гинекологическое",
    "Кресло медицинское",
    "Кровать медицинская",
    "Кушетка медицинская",
    "Негатоскоп",
    "Носилки медицинские",
    "Облучатель бактерицидный",
    "Облучатель физиотерапевтический",
    "Парафинонагреватель",
    "Подставка медицинская",
    "Рециркулятор бактерицидный",
    "Ростомер медицинский",
    "Стерилизатор медицинский",
    "Стойка медицинская",
    "Стол массажный",
    "Стол медицинский",
    "Столик медицинский",
    "Стул медицинский",
    "Сумка медицинская",
    "Таблица для проверки зрения",
    "Термостат медицинский",
    "Тележка медицинская",
    "Тумба медицинская",
    "Шкаф медицинский",
    "Ширма медицинская",
    "Штатив медицинский",
]

# Переменные для контроля попыток
success = False  # Флаг успешного завершения
max_attempts = 5  # Количество попыток
attempts = 0  # Счетчик попыток

while attempts < max_attempts:
    attempts += 1
    try:
        # Запуск Selenium
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=chrome_options
        )

        data = []
        today_date = datetime.today().strftime("%Y-%m-%d")

        for query in queries:
            url = f"https://prom.ua/search?search_term={query.replace(' ', '%20')}"
            driver.get(url)
            time.sleep(5)

            # Прокрутка страницы для загрузки всех элементов
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            companies = soup.find_all("span", {"data-qaid": "company_name"})
            products = soup.find_all("a", {"data-qaid": "product_link"})
            prices = soup.find_all("div", {"data-qaid": "product_price"})

            for index, (company, product, price) in enumerate(
                zip(companies, products, prices), 1
            ):
                company_name = company.get_text(strip=True)
                product_name = product.get("title", "Неизвестное название")
                product_link = product.get("href", "Нет ссылки")
                if not product_link.startswith("http"):
                    product_link = "https://prom.ua" + product_link

                product_price = (
                    price.find("span", class_="yzKb6")
                    .get_text(strip=True)
                    .replace("\xa0", " ")
                    if price and price.find("span", class_="yzKb6")
                    else "Цена не указана"
                )

                data.append(
                    [
                        today_date,
                        query,
                        index,
                        company_name,
                        product_name,
                        product_price,
                        product_link,
                    ]
                )

        # Сохранение в Google-таблицу
        if data:
            sheet_data = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=SPREADSHEET_ID, range="Лист1")
                .execute()
                .get("values", [])
            )

            last_row = len(sheet_data)
            range_name = f"Лист1!A{last_row + 1}"

            body = {"values": data}
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=range_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()

        success = True  # Успешное выполнение
        break  # Выход из цикла после успешной попытки

    except Exception as e:
        logging.error(f"Попытка {attempts}: Ошибка во время выполнения скрипта: {e}")
        time.sleep(10)  # Задержка перед повторной попыткой

    finally:
        if "driver" in locals():
            driver.quit()

# Отправка сообщений в Telegram
if success:
    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, "Скрипт завершён успешно")
else:
    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, "scraper")

print("Скрипт завершён.")
