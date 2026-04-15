import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

# 頁面設定：徹底隱藏 Sidebar，寬屏佈局
st.set_page_config(
    page_title="TCG Master Quant Pro",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 1. 終極 CSS (包含正宗大師球造型、強光特效、完美對齊排版) ---
st.markdown("""
    <style>
    /* 隱藏 Sidebar */
    [data-testid="stSidebarNav"] {display: none;}
    section[data-testid="stSidebar"] {display: none;}
    .stAppDeployButton {display: none;}

    /* 全螢幕閃光動畫 */
    @keyframes flash {
        0% { opacity: 0; background-color: #ffffff; }
        50% { opacity: 1; background-color: #ffffff; }
        100% { opacity: 0; }
    }
    .flash-effect {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        z-index: 9999; pointer-events: none; animation: flash 0.6s ease-out;
    }

    /* 正宗大師球按鈕：紫上、白下、黑帶、紅耳 */
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%) !important;
        color: #ffffff !important;
        border-radius: 50% !important;
        width: 240px !important;
        height: 240px !important;
        border: 12px solid #333 !important;
        font-size: 140px !important; /* M 字巨型化 */
        font-weight: 900 !important;
        box-shadow: 0 15px 45px rgba(0,0,0,0.4) !important;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        line-height: 1 !important;
        padding-bottom: 95px !important; /* M 字托上紫色位 */
        position: relative !important;
        z-index: 10 !important;
        margin: 20px auto !important;
        display: block !important;
        text-shadow: 3px 5px 15px rgba(0,0,0,0.3) !important;
    }
    
    /* 大師球耳仔 (紅色) */
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: ""; position: absolute; width: 45px; height: 25px;
        background: #ff004f; top: 20%; border-radius: 50%; z-index: -1;
    }
    div.stButton > button:first-child::before { left: 20px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 20px; transform: rotate(35deg); }

    div.stButton > button:first-child:hover {
        transform: scale(1.05) rotate(5deg) !important;
        box-shadow: 0 20px 55px rgba(123, 44, 191, 0.6) !important;
    }

    /* 數據卡片：完美左右對齊 */
    .price-card {
        border: 2px solid #7b2cbf;
        padding: 18px;
        border-radius: 15px;
        background-color: #fcfaff;
        box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 25px;
        min-width: 250px;
    }
    .price-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        width: 100%;
    }
    .price-label {
        font-weight: bold;
        color: #555;
        font-size: 15px;
        white-space: nowrap; /* 禁止換行 */
    }
    .price-val {
        font-weight: 900;
        color: #000;
        font-size: 17px;
        text-align: right;
        flex-grow: 1;
        margin-left: 10px;
    }
    .price-sep {
        border-top: 1px dashed #7b2cbf;
        margin: 12px 0;
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Google Sheet 連接 (加強穩定性)
@st.cache_resource
def connect_gsheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
        ss = client.open_by_key(SHEET_ID)
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

# 3. 爬蟲核心 (Turbo 極速版)
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        # 阻擋非必要資源提速
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2}", lambda route: route.abort())
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("#price-table-body td", timeout=15000)
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            p_list = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            tbody = soup.find('tbody', id='price-table-body')
            if tbody:
                tds = tbody.find_all('td')
                if len(tds) >= 4:
                    p_list["美品"], p_list["PSA10"], p_list["差額"], p_list["比率"] = tds[0].text, tds[1].text, tds[2].text, tds[3].text
            
            return {"名稱": name, "圖片": img_url, **p_list}
        except:
            return None
        finally:
            browser.close()

# 4. 頂部導航欄 (控制台移至右上角)
head_col, ctrl_col = st.columns([6, 1.2])

with head_col:
    st.title("🛡️ TCG Master Quant Pro")

with ctrl_col:
    with st.popover("⚙️ 控制台", use_container_width=True):
        pw = st.text_input("輸入授權碼", type="password")
        if main_sheet:
            current_urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
            if pw == st.secrets.get("admin_password", "8888"):
                st.success("身分確認")
                new_urls = st.text_area("監控名單:", value="\n".join(current_urls), height=250)
                if st.button("💾 儲存並同步"):
                    main_sheet.clear()
                    rows = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
                    if rows: main_sheet.update('A1', rows)
                    st.cache_data.clear()
                    st.rerun()

# 5. 主介面：正宗大師球
st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
_, ball_mid, _ = st.columns([1, 1, 1])

with ball_mid:
    if st.button("M", key="master_ball_final"):
        if main_sheet:
            urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
            if urls:
                results = []
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                status = st.status("🔮 大師球捕捉中...", expanded=True)
                for url in urls:
                    status.write(f"正在掃瞄：{url.split('/')[-1]}")
                    res = fetch_data(url)
                    if res: results.append(res)
                status.update(label="💥 捕捉完成！", state="complete", expanded=False)
                
                if results:
                    st.markdown('<div class="flash-effect"></div>', unsafe_allow_html=True)
                    if history_sheet:
                        h_rows = [[now, r["名稱"], r["圖片"], r["PSA10"], r["美品"], r["差額"], r["比率"]] for r in results]
                        history_sheet.append_rows(h_rows)
                    
                    st.divider()
                    grid = st.columns(3)
                    for i, item in enumerate(results):
                        with grid[i % 3]:
                            st.image(item["圖片"], use_container_width=True)
                            st.markdown(f"**{item['名稱']}**")
                            # 終極完美排版數據框
                            card_html = f"""
                            <div class="price-card">
                                <div class="price-row"><span class="price-label" style="color:#e67e22;">● 美品價格</span><span class="price-val">{item['美品']}</span></div>
                                <div class="price-row"><span class="price-label" style="color:#3498db;">● PSA10價格</span><span class="price-val">{item['PSA10']}</span></div>
                                <div class="price-sep"></div>
                                <div class="price-row"><span class="price-label">● 差額</span><span class="price-val">{item['差額']}</span></div>
                                <div class="price-row"><span class="price-label">● 比率</span><span class="price-val">{item['比率']}</span></div>
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.warning("名單內無網址。")
        else:
            st.error("Sheet 連接失敗")
    else:
        st.info("💡 準備就緒。點擊大師球啟動捕捉。")

st.divider()
st.caption("阿強 TCG Cloud Pro | 2026 終極完美版")
