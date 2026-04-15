import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from datetime import datetime

st.set_page_config(page_title="TCG Master Ball Quant", page_icon="🔮", layout="wide")

# --- 1. 終極大師球 3.1 CSS ---
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 50%, #ffffff 50%);
        color: #ffffff;
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
        line-height: 0.1;
        padding-bottom: 90px;
        position: relative;
    }
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
    div.stButton > button:first-child:hover { transform: scale(1.08) rotate(5deg); }
    .master-label { text-align: center; font-weight: 900; color: #7b2cbf; font-size: 26px; margin-top: -10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. Google Sheet 連接 (加強除錯) ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    if "gcp_service_account" not in st.secrets:
        st.error("❌ Streamlit Secrets 入面搵唔到 'gcp_service_account'！請檢查 Settings > Secrets。")
        st.stop()
        
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    
    # 嘗試打開 Spreadsheet
    spreadsheet = client.open_by_key(SHEET_ID)
    main_sheet = spreadsheet.sheet1
    
    # 嘗試打開 History 分頁
    try:
        history_sheet = spreadsheet.worksheet("History")
    except:
        st.warning("⚠️ 搵唔到名為 'History' 的分頁，請確保 Google Sheet 下方有個 Tab 叫 History (大細階要啱)。")
        history_sheet = None

except Exception as e:
    st.error(f"❌ Google Sheet 連接失敗: {e}")
    st.info("💡 請檢查：\n1. Secrets 格式有無貼錯\n2. 係咪已經將 Sheet share 畀 tcg-robot@... 嗰個 Email 並設為「編輯者」")
    st.stop()

# --- 3. 爬蟲核心 (對準 price-table-body) ---
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
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # 等候數據填入
            page.wait_for_selector("#price-table-body td:has-text('円')", timeout=20000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
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

# --- 4. UI 介面 ---
st.title("🛡️ TCG Master Ball Quant 3.1")

urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]

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
                res = fetch_master_ball_data(url)
                if res: results.append(res)
                bar.progress((i + 1) / len(urls))
            status.success(f"✅ 捕捉完畢！最後更新: {now}")
            
            if results:
                if history_sheet:
                    h_rows = [[now, r["名稱"], f'=IMAGE("{r["圖片"]}")', r["PSA10"], r["美品"], r["差額"], r["比率"]] for r in results]
                    history_sheet.append_rows(h_rows)
                
                st.divider()
                grid = st.columns(3)
                for idx, item in enumerate(results):
                    with grid[idx % 3]:
                        st.image(item["圖片"], use_container_width=True)
                        st.markdown(f"**{item['名稱']}**")
                        st.markdown(f"""
                        <div style="font-size: 15px; border: 3px solid #7b2cbf; padding: 15px; border-radius: 15px; background-color: #fcfaff;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;"><span style="color: #e67e22; font-weight: bold;">● 美品：</span><b>{item['美品']}</b></div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;"><span style="color: #3498db; font-weight: bold;">● PSA10：</span><b>{item['PSA10']}</b></div>
                            <div style="border-top: 2px dashed #7b2cbf; margin-top: 10px; padding-top: 10px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;"><span style="color: #666;">● 差額：</span><b>{item['差額']}</b></div>
                                <div style="display: flex; justify-content: space-between;"><span style="color: #666;">● 比率：</span><b>{item['比率']}</b></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                st.balloons()
    st.markdown('<p class="master-label">MASTER BALL UPDATE</p>', unsafe_allow_html=True)

st.divider()
st.caption("阿強 TCG Cloud Pro | 2026 穩定除錯版")
