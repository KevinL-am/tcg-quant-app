import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

st.set_page_config(page_title="TCG Master Quant Pro", page_icon="🔮", layout="wide")

# --- 1. 終極 CSS：大師球特效、強光動畫、完美居中 ---
st.markdown("""
    <style>
    /* 全螢幕強光閃爍動畫 */
    @keyframes flash {
        0% { opacity: 0; background-color: white; }
        50% { opacity: 1; background-color: white; }
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

    /* 確保按鈕容器完美居中 */
    .stButton {
        display: flex;
        justify-content: center;
        margin-top: 20px;
    }

    /* 大師球按鈕：M字加大、造型更細緻 */
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 50%, #ffffff 50%);
        color: #ffffff !important;
        border-radius: 50%;
        width: 220px;
        height: 220px;
        border: 12px solid #333;
        font-size: 130px !important; /* M字更震撼 */
        font-weight: 900;
        box-shadow: 0 15px 35px rgba(123, 44, 191, 0.5);
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        line-height: 0.1;
        padding-bottom: 95px;
        position: relative;
        text-shadow: 2px 4px 10px rgba(0,0,0,0.3);
    }
    
    div.stButton > button:first-child:hover {
        transform: scale(1.1) rotate(5deg);
        border-color: #ff0000;
        box-shadow: 0 20px 45px rgba(123, 44, 191, 0.8);
    }

    div.stButton > button:first-child:active {
        transform: scale(0.95);
    }

    .master-label {
        text-align: center;
        font-weight: 900;
        color: #7b2cbf;
        font-size: 26px;
        letter-spacing: 4px;
        margin-top: 10px;
        text-transform: uppercase;
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
    .row { display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center; }
    .label { font-weight: bold; color: #555; }
    .val { font-weight: 900; color: #000; font-size: 16px; }
    .divider { border-top: 1px dashed #7b2cbf; margin: 10px 0; }
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

# --- 3. 爬蟲核心 (Turbo 極速版：阻擋圖片加載) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_master_data_turbo(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        # 🚀 極速優化：唔 Load 圖片、字體同廣告
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2}", lambda route: route.abort())
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # 認住個數據 Body
            page.wait_for_selector("#price-table-body td", timeout=15000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            
            # 圖片網址 (雖然我哋無 Load 圖，但網址仲喺 HTML 度)
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"

            data = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            tbody = soup.find('tbody', id='price-table-body')
            if tbody:
                tds = tbody.find_all('td')
                if len(tds) >= 4:
                    data["美品"] = tds[0].get_text(strip=True)
                    data["PSA10"] = tds[1].get_text(strip=True)
                    data["差額"] = tds[2].get_text(strip=True)
                    data["比率"] = tds[3].get_text(strip=True)
            return {"名稱": name, "圖片": img_url, **data}
        except: return None
        finally: browser.close()

# --- 4. Sidebar 名單管理 ---
st.sidebar.title("💎 TCG Master Ball Admin")
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("🔑 大師授權碼", type="password")
urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]

if pw == REAL_PW:
    st.sidebar.success("✅ 授權成功")
    new_urls = st.sidebar.text_area("🔧 監控清單:", value="\n".join(urls), height=300)
    if st.sidebar.button("💾 儲存並同步名單"):
        main_sheet.clear()
        rows = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear()
        st.rerun()

# --- 5. 主介面：大師球更新 ---
st.title("🛡️ TCG Master Quant Pro")

# 居中按鈕
update_clicked = st.button("M")
st.markdown('<p class="master-label">Master Ball Update</p>', unsafe_allow_html=True)

if update_clicked:
    if not urls:
        st.warning("名單內無網址。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 炫酷進度條
        status_box = st.status("🔮 大師球正在收集能量...", expanded=True)
        for i, url in enumerate(urls):
            status_box.write(f"正在掃瞄：{url.split('/')[-1]}")
            data = fetch_master_data_turbo(url)
            if data: results.append(data)
        status_box.update(label="💥 捕捉完成！數據正在爆發...", state="complete", expanded=False)

        if results:
            # 顯示閃光特效
            st.markdown('<div class="flash-effect"></div>', unsafe_allow_html=True)
            
            # 儲存到歷史
            h_rows = [[now, r["名稱"], f'=IMAGE("{r["圖片"]}")', r["PSA10"], r["美品"], r["差額"], r["比率"]] for r in results]
            history_sheet.append_rows(h_rows)
            
            # 展示成果
            st.divider()
            grid = st.columns(3)
            for idx, item in enumerate(results):
                with grid[idx % 3]:
                    st.image(item["圖片"], use_container_width=True)
                    st.markdown(f"**{item['名稱']}**")
                    st.markdown(f"""
                    <div class="price-box">
                        <div class
