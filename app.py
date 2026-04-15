import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

# 頁面基本設定：強制隱藏 sidebar
st.set_page_config(page_title="TCG Master Ball Pro", page_icon="🔮", layout="wide", initial_sidebar_state="collapsed")

# --- 1. 終極「正宗大師球」與「頂部佈局」CSS ---
st.markdown("""
    <style>
    /* 隱藏左邊 sidebar 標誌 */
    [data-testid="stSidebarNav"] {display: none;}
    section[data-testid="stSidebar"] {display: none;}

    /* 全螢幕閃光動畫 */
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

    /* 大師球容器居中 */
    .master-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        padding: 20px 0;
    }

    /* 正宗大師球按鈕 */
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%);
        color: #ffffff !important;
        border-radius: 50%;
        width: 250px;
        height: 250px;
        border: 12px solid #333;
        font-size: 150px !important;
        font-weight: 900;
        box-shadow: 0 15px 45px rgba(0,0,0,0.4);
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        line-height: 0.1;
        padding-bottom: 110px;
        position: relative;
        text-shadow: 3px 5px 15px rgba(0,0,0,0.3);
    }
    
    /* 大師球左右耳仔 */
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: "";
        position: absolute;
        width: 50px;
        height: 30px;
        background: #ff004f;
        top: 20%;
        border-radius: 50%;
    }
    div.stButton > button:first-child::before { left: 15px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 15px; transform: rotate(35deg); }

    div.stButton > button:first-child:hover {
        transform: scale(1.05) rotate(5deg);
        box-shadow: 0 20px 50px rgba(123, 44, 191, 0.6);
    }

    /* 數據卡片排版 */
    .price-card {
        border: 2px solid #7b2cbf;
        padding: 15px;
        border-radius: 15px;
        background-color: #fcfaff;
        box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .price-row { display: flex; justify-content: space-between; margin-bottom: 8px; }
    .price-label { font-weight: bold; color: #555; }
    .price-val { font-weight: 900; color: #000; }
    .price-sep { border-top: 1px dashed #7b2cbf; margin: 10px 0; }
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

# --- 3. 爬蟲核心 (Turbo 極速版) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_master_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        # 阻擋非必要資源
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2}", lambda route: route.abort())
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("#price-table-body td", timeout=15000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            name_text = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"

            prices = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            tbody = soup.find('tbody', id='price-table-body')
            if tbody:
                tds = tbody.find_all('td')
                if len(tds) >= 4:
                    prices["美品"] = tds[0].get_text(strip=True)
                    prices["PSA10"] = tds[1].get_text(strip=True)
                    prices["差額"] = tds[2].get_text(strip=True)
                    prices["比率"] = tds[3].get_text(strip=True)
            
            return {"名稱": name_text, "圖片": img_url, **prices}
        except: return None
        finally: browser.close()

# --- 4. 頂部導航欄 (替代 Sidebar) ---
header_col, control_col = st.columns([5, 1.2])

with header_col:
    st.title("🛡️ TCG Master Quant Pro")

with control_col:
    # 呢度就係大佬要嘅「控制台」，擺喺右邊好似 Share 旁邊咁
    with st.popover("控制台 ⚙️", use_container_width=True):
        st.write("### 🔑 安全驗證")
        REAL_PW = st.secrets.get("admin_password", "8888")
