import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 1. 頁面設定：徹底隱藏 Sidebar，寬屏佈局
st.set_page_config(
    page_title="TCG Master Quant Pro",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. 終極 CSS (正宗大師球、閃光特效、港幣專屬樣式) ---
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    section[data-testid="stSidebar"] {display: none;}
    .stAppDeployButton {display: none;}

    @keyframes flash {
        0% { opacity: 0; background-color: #ffffff; }
        50% { opacity: 1; background-color: #ffffff; }
        100% { opacity: 0; }
    }
    .flash-effect {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        z-index: 9999; pointer-events: none; animation: flash 0.6s ease-out;
    }

    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%) !important;
        color: #ffffff !important;
        border-radius: 50% !important;
        width: 200px !important;
        height: 200px !important;
        border: 10px solid #333 !important;
        font-size: 110px !important;
        font-weight: 900 !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.4) !important;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        line-height: 1 !important;
        padding-bottom: 80px !important;
        position: relative !important;
        z-index: 100 !important;
        margin: 20px auto !important;
        display: block !important;
    }
    
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: ""; position: absolute; width: 40px; height: 20px;
        background: #ff004f; top: 22%; border-radius: 50%; z-index: -1;
    }
    div.stButton > button:first-child::before { left: 10px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 10px; transform: rotate(35deg); }

    .price-card {
        border: 2px solid #7b2cbf;
        padding: 15px;
        border-radius: 15px;
        background-color: #fcfaff;
        box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .price-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; width: 100%; }
    .price-label { font-weight: bold; color: #555; font-size: 13px; }
    .price-val { font-weight: 900; color: #000; font-size: 15px; text-align: right; }
    .hkd-val { font-weight: 900; color: #b8860b; font-size: 15px; text-align: right; }
    .price-sep { border-top: 1px dashed #7b2cbf; margin: 8px 0; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# 3. 輔助函數：解析日元數字
def parse_yen(yen_str):
    try:
        if not yen_str or "N/A" in yen_str: return 0
        num_str = re.sub(r'[^\d]', '', yen_str)
        return float(num_str) if num_str else 0
    except:
        return 0

# 4. Google Sheet 連接 (已更新 ID)
@st.cache_resource
def connect_gsheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        # ✅ 第 89 行：已換上大佬的新 Sheet ID
        ss = client.open_by_key("1gGDyFS3Ecq0h45zvVpV72ZimxKvrY-HhNUB4IBLNG4")
        main = ss.sheet1
        try:
            hist = ss.worksheet("History")
        except:
            hist = ss.add_worksheet(title="History", rows="1000", cols="20")
            hist.append_row(["更新時間", "名稱", "圖片", "PSA10", "美品", "差額", "比率"])
        return main, hist
    except:
        return None, None

main_sheet, history_sheet = connect_gsheet()

# 5. 爬蟲核心
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0")
        page = context.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2}", lambda route: route.abort())
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("#price-table-body td", timeout=15000)
            soup = BeautifulSoup(page.content(), 'html.parser')
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img:
                src = img.get('src') or img.get('data-src')
                img_url = src if src and src.startswith('http') else f"https://grading.pokeca-chart.com{src}" if src else "N/A"
            
            p_list = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            tbody = soup.find('tbody', id='price-table-body')
            if tbody:
                tds = tbody.find_all('td')
                if len(tds) >= 4:
                    p_list["美品"], p_list["PSA10"], p_list["差額"], p_list["比率"] = tds[0].text, tds[1].text, tds[2].text, tds[3].text
            return {"名稱": name, "圖片": img_url, "美品": p_list["美品"], "PSA10": p_list["PSA10"], "差額": p_list["差額"],
