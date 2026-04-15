import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

# 1. 頁面設定：隱藏 sidebar，設定 layout
st.set_page_config(page_title="TCG Master Quant Pro", page_icon="🔮", layout="wide", initial_sidebar_state="collapsed")

# 2. 終極 CSS (修復 Click 唔到嘅問題)
st.markdown("""
    <style>
    /* 徹底隱藏 sidebar */
    [data-testid="stSidebarNav"] {display: none;}
    section[data-testid="stSidebar"] {display: none;}

    /* 閃光動畫 */
    @keyframes flash {
        0% { opacity: 0; background-color: #ffffff; }
        50% { opacity: 1; background-color: #ffffff; }
        100% { opacity: 0; }
    }
    .flash-effect {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        z-index: 9999; pointer-events: none; animation: flash 0.6s ease-out;
    }

    /* 正宗大師球按鈕 */
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%) !important;
        color: #ffffff !important;
        border-radius: 50% !important;
        width: 200px !important;
        height: 200px !important;
        border: 10px solid #333 !important;
        font-size: 110px !important;
        font-weight: 900 !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.4) !important;
        transition: all 0.2s ease !important;
        line-height: 1 !important;
        padding-bottom: 80px !important;
        position: relative !important;
        z-index: 100 !important; /* 確保喺最頂層 */
        margin: 0 auto !important;
        display: block !important;
    }
    
    /* 大師球紅色耳仔 */
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: ""; position: absolute; width: 40px; height: 20px;
        background: #ff004f; top: 20%; border-radius: 50%; z-index: -1;
    }
    div.stButton > button:first-child::before { left: 10px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 10px; transform: rotate(35deg); }

    div.stButton > button:first-child:hover {
        transform: scale(1.05) !important;
        box-shadow: 0 15px 40px rgba(123, 44, 191, 0.6) !important;
    }

    /* 數據框排版 */
    .price-card {
        border: 2px solid #7b2cbf; padding: 15px; border-radius: 15px;
        background-color: #fcfaff; box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .price-row { display: flex; justify-content: space-between; margin-bottom: 8px; }
    .price-label { font-weight: bold; color: #555; }
    .price-val { font-weight: 900; color: #000; }
    </style>
""", unsafe_allow_html=True)

# 3. Google Sheet 連接
@st.cache_resource
def connect_gsheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
        ss = client.open_by_key(SHEET_ID)
        main = ss.sheet1
        try: hist = ss.worksheet("History")
        except: 
            hist = ss.add_worksheet(title="History", rows="1000", cols="20")
            hist.append_row(["更新時間", "名稱", "圖片", "PSA10", "美品", "差額", "比率"])
        return main, hist
    except Exception as e:
        st.error(f"❌ Google Sheet 連接失敗: {e}")
        return None, None

main_sheet, history_sheet = connect_gsheet()

# 4. 爬蟲
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2}", lambda route: route.abort())
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("#price-table-body td", timeout=15000)
