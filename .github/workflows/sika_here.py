# env:
#           chat: ${{ secrets.CHAT_TOKEN }}
#           sedinam: ${{ secrets.CHAT_TOKEN_ID_SEDINAM }}
#           sanbenito: ${{ secrets.CHAT_TOKEN_ID_SANBENITO }}
#           wenow_url : ${{ secrets.CHAT_TOKEN_URL }}
#         run: python sika_script.py

import os
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def clean_text(text):
    """Applies your regex logic to the scraped data"""
    no_letters = re.sub(r'[a-zA-Z]', '', text)
    no_capitals = re.sub(r'[A-Z]', '', text)
    return no_letters, no_capitals

def send_telegram(message):
    """Sends the result to your Telegram bot"""
    token = os.environ.get("chat")
    sedinam = os.environ.get("sedinam")
    sanbenito = os.environ.get("sanbenito")
    wenow_url = os.environ.get("wenow_url")
  
    
    if not token or not sedinam:
        print("Error: Telegram credentials missing!")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": sedinam, "text": message}
    requests.post(url, data=payload)

def main():
    # Setup Headless Chrome for GitHub Actions environment
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Required for cloud servers
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Automatically manages the driver version
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=chrome_options
    )

    try:
        driver.get("https://www.google.com/search?q=wwe")
        raw_text = driver.title 
        processed_1, processed_2 = clean_text(raw_text)
        
        final_msg = f"Original: {raw_text}\nNo Letters: {processed_1}\nNo Capitals: {processed_2}"
        send_telegram(final_msg)
        print("Message sent successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
        raw_text = "fgfghgn3577667vcfASDS2032"
        processed_1, processed_2 = clean_text(raw_text)
        
        final_msg = f"Original: {raw_text}\nNo Letters: {processed_1}\nNo Capitals: {processed_2}"
        send_telegram(final_msg)
        print("Message sent successfully!")
    finally:
        driver.quit()


main()
# raw_text = "fgfghgn3577667vcfASDS2032"
# processed_1, processed_2 = clean_text(raw_text)
    
# final_msg = f"Original: {raw_text}\nNo Letters: {processed_1}\nNo Capitals: {processed_2}"
# send_telegram(final_msg)
# print("Message sent successfully!")

# import os
# import re
# import requests
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager

# def clean_text(text):
#     """Applies your regex logic to the scraped data"""
#     no_letters = re.sub(r'[a-zA-Z]', '', text)
#     no_capitals = re.sub(r'[A-Z]', '', text)
#     return no_letters, no_capitals

# def send_telegram(message):
#     """Sends the result to your Telegram bot"""
#     token = os.environ.get("TELEGRAM_TOKEN")
#     chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
#     if not token or not chat_id:
#         print("Error: Telegram credentials missing!")
#         return

#     url = f"https://api.telegram.org/bot{token}/sendMessage"
#     payload = {"chat_id": chat_id, "text": message}
#     requests.post(url, data=payload)

# def main():
#     # Setup Headless Chrome for GitHub Actions environment
#     chrome_options = Options()
#     chrome_options.add_argument("--headless=new")  # Required for cloud servers
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
    
#     # Automatically manages the driver version
#     driver = webdriver.Chrome(
#         service=Service(ChromeDriverManager().install()), 
#         options=chrome_options
#     )

#     try:
#         driver.get("https://www.google.com")
#         raw_text = driver.title 
#         processed_1, processed_2 = clean_text(raw_text)
        
#         final_msg = f"Original: {raw_text}\nNo Letters: {processed_1}\nNo Capitals: {processed_2}"
#         send_telegram(final_msg)
#         print("Message sent successfully!")

#     except Exception as e:
#         print(f"An error occurred: {e}")
#     finally:
#         driver.quit()

# if __name__ == "__main__":
#     main()


