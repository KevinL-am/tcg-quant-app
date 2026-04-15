import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

# 頁面基本設定
st.set_page_config(page_title="TCG Master Quant Pro", page_icon="🔮", layout="wide")

# --- 1. 終極「正宗」大師球 CSS ---
st.markdown("""
    <style>
    /* 全螢幕閃光動畫 (Master Ball Burst) */
    @keyframes flash {
        0% { opacity: 0; background-color: #ffffff; }
        50% { opacity: 1; background-color: #ffffff; }
        100% { opacity: 0; }
    }
    .flash-effect {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        z-index: 9999;
        pointer-events: none;
        animation: flash 0.6s ease-out;
    }

    /* 容器居中：確保球同字都喺正中間 */
    .master-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        margin: 40px auto;
        width: 100%;
    }

    /* 正宗大師球按鈕 */
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%);
        color: #ffffff !important;
        border-radius: 50%;
        width: 250px;
        height: 250px;
        border: 12px solid #333;
        font-size: 150px !important; /* 巨型 M 字 */
        font-weight: 900;
        box-shadow: 0 15px 40px rgba(0,0,0,0.4);
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        line-height: 1;
        padding-bottom: 110px; /* 將 M 字托上去紫色區 */
        position: relative;
        text-shadow: 3px 5px 15px rgba(0,0,0,0.4);
        z-index: 1;
        margin: 0 auto;
    }
    
    /* 大師球兩邊嘅紅色正宗特徵 */
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: "";
        position: absolute;
        width: 45px;
        height: 25px;
        background: #ff004f;
        top: 20%;
        border-radius: 50%;
        z-index: -1;
    }
    div.stButton > button:first-child::before { left: 15px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 15px; transform: rotate(35deg); }

    div.stButton > button:first-child:hover {
        transform: scale(1.1) rotate(5deg);
        box-shadow: 0 20px 50px rgba(123, 44, 191, 0.6);
    }

    .master-label {
        font-weight: 900;
        color: #7b2cbf;
        font-size: 28px;
        letter-spacing: 5px;
        text-transform: uppercase;
        margin-top: 20px;
        width: 100%;
        display: block;
    }

    /* 數據框整潔排版 */
    .price-box {
        font-size: 15px; 
        border: 2px solid #7b2cbf; 
        padding: 15px; 
        border-radius: 15px; 
        background-color: #fcfaff; 
        box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
    }
    .data-row { display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center; }
    .label-text { font-weight: bold; color: #555; }
    .val-text { font-weight: 900; color: #000; font-size: 16px; }
    .line-sep { border-top: 1px dashed #7b2cbf; margin: 10px 0; }
    </style>
""", unsafe_allow_html=True)

# --- 2. Google Sheet 連接 ---
@st.cache_resource
def connect_gsheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    spreadsheet = client.open_by_key(SHEET_ID)
    main = spreadsheet.sheet1
    try:
        hist = spreadsheet.worksheet("History")
    except:
        hist = spreadsheet.add_worksheet(title="History", rows="1000", cols="20")
        hist.append_row(["更新時間", "名稱", "圖片", "PSA10", "美品", "差額", "比率"])
    return main, hist

main_sheet, history_sheet = connect_gsheet()

# --- 3. 爬蟲核心 ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        # 阻擋資源提速
        page.route("**/*.{png,jpg,jpeg,gif
