import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from datetime import datetime

st.set_page_config(page_title="TCG Master Ball Quant", page_icon="🔮", layout="wide")

# --- 1. 終極大師球 3.0 CSS (完美還原配色) ---
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 50%, #ffffff 50%); /* 紫色上, 白色下 */
        color: #ffffff; /* M 字白色 */
        border-radius: 50%;
        width: 200px;
        height: 200px;
        border: 12px solid #333;
        font-size: 100px !important;
        font-weight: 900;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        display: block;
        margin: 20px auto;
        transition: all 0.2s ease;
        line-height: 0.1; /* 將 M 字托上去紫色區域 */
        padding-bottom: 90px;
        position: relative;
    }
    /* 大師球側邊兩粒粉紅/紅色特徵 */
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: "";
        position: absolute;
        width: 35px;
        height: 15px;
        background: #ff4d4d;
        top: 25%;
        border-radius: 10px;
    }
    div.stButton > button:first-child::before { left: 15px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 15px; transform: rotate(35deg); }

    div.stButton > button:first-child:hover {
        transform: scale(1.08) rotate(5deg);
        box-shadow: 0 15px 35px rgba(123, 44, 191, 0.6);
    }
    .master-label {
        text-align: center;
        font-weight: 900;
        color: #7b2cbf;
        font-size: 26px;
        letter-spacing: 2px;
        margin-top: -10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. Google Sheet 連接 ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    main_sheet = client.open_by_key(SHEET_ID).sheet1
    history_sheet = client.open_by_key(SHEET_ID).worksheet("History")
except Exception as e:
    st.error("❌ Google Sheet 連接失敗")
    st.stop()

# --- 3. 終極爬蟲核心 (對準 price-table-body) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_master_ball_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        try:
            # 1. 直接衝入去
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 2. ⚡ 關鍵：等候 ID 係 price-table-body 嘅地方出現「円」字
            # 呢個動作係等 JavaScript 將數據填入去
            page.wait_for_selector("#price-table-body td:has-text('円')", timeout=20000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # --- 捉名同圖 ---
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"

            # --- 💡 根據大佬提供嘅截圖定位 ---
            data = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            
            # 喺 price-table-body 入面搵 <td>
            tbody = soup.find('tbody', id='price-table-body')
            if tbody:
                tds = tbody.find_all('td')
                # 根據網頁排列順序: 美品(0), PSA10(1), 差額(2), 比率(3)
                if len(tds) >= 4:
                    data["美品"] = tds[0].get_text(strip=True)
                    data["PSA10"] = tds[1].get_text(strip=True)
                    data["差額"] = tds[2].get_text(strip=True)
                    data["比率"] = tds[3].get_text(strip=True)

            return {"名稱": name, "圖片": img_url, **data}
        except:
            return None
        finally:
            browser.close()

# --- 4. UI 介面 ---
st.title("🛡️ TCG Master Ball Quant 3.0")

urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]

# 居中大師球按鈕
st.write("")
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("M"):
        if not urls:
            st.warning("名單係空嘅。")
        else:
            results = []
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            bar = st.progress(0)
            status = st.empty()
            
            for i, url in enumerate(urls):
                status.write(f"🔮 大師球捕捉中 ({i+1}/{len(urls)})...")
                res = fetch_
