import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

# 1. 頁面設定：徹底隱藏 Sidebar，寬屏佈局
st.set_page_config(
    page_title="TCG Master Quant Pro",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. 終極 CSS (正宗大師球、強光爆裂、完美對齊排版) ---
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

    /* 正宗大師球按鈕：紫上、白底、黑腰帶、紅耳 */
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%) !important;
        color: #ffffff !important;
        border-radius: 50% !important;
        width: 240px !important;
        height: 240px !important;
        border: 12px solid #333 !important;
        font-size: 140px !important;
        font-weight: 900 !important;
        box-shadow: 0 15px 45px rgba(0,0,0,0.4) !important;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        line-height: 1 !important;
        padding-bottom: 95px !important;
        position: relative !important;
        z-index: 100 !important;
        margin: 20px auto !important;
        display: block !important;
        text-shadow: 3px 5px 15px rgba(0,0,0,0.3) !important;
    }
    
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: ""; position: absolute; width: 45px; height: 25px;
        background: #ff004f; top: 22%; border-radius: 50%; z-index: -1;
    }
    div.stButton > button:first-child::before { left: 15px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 15px; transform: rotate(35deg); }

    /* 數據卡片排版 */
    .price-card {
        border: 2px solid #7b2cbf;
        padding: 18px;
        border-radius: 15px;
        background-color: #fcfaff;
        box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 25px;
    }
    .price-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        width: 100%;
    }
    .price-label { font-weight: bold; color: #555; font-size: 15px; white-space: nowrap; }
    .price-val { font-weight: 900; color: #000; font-size: 17px; text-align: right; flex-grow: 1; margin-left: 10px; }
    .price-sep { border-top: 1px dashed #7b2cbf; margin: 12px 0; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# 3. Google Sheet 連接
@st.cache_resource
def connect_gsheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key("1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM")
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

# 4. 爬蟲核心
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
            
            return {"名稱": name, "圖片": img_url, "美品": p_list["美品"], "PSA10": p_list["PSA10"], "差額": p_list["差額"], "比率": p_list["比率"]}
        except:
            return None
        finally:
            browser.close()

# 5. 頂部導航
head_col, ctrl_col = st.columns([6, 1.5])
with head_col: st.title("🛡️ TCG Master Quant Pro")
with ctrl_col:
    with st.popover("⚙️ 控制台", use_container_width=True):
        pw = st.text_input("授權碼", type="password")
        if main_sheet and pw == st.secrets.get("admin_password", "8888"):
            urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
            new_urls = st.text_area("監控名單:", value="\n".join(urls), height=250)
            if st.button("💾 儲存並同步"):
                main_sheet.clear()
                main_sheet.update('A1', [[u.strip()] for u in new_urls.split("\n") if u.strip()])
                st.cache_data.clear()
                st.rerun()

# 6. 主介面：大師球
st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)

# ✅ 修正位：確保括號正確關閉
_, ball_mid, _ = st.columns([1, 1, 1])
with ball_mid:
    start_capture = st.button("M", key="master_ball_vfinal")

# 7. 流式加載邏輯
if start_capture:
    urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
    if not urls:
        st.warning("名單係空嘅。")
    else:
        st.markdown('<div class="flash-effect"></div>', unsafe_allow_html=True)
        all_results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        status = st.status("🔮 大師球捕捉中...", expanded=True)
        
        current_batch = []
        display_area = st.container()

        for i, url in enumerate(urls):
            status.write(f"掃瞄 ({i+1}/{len(urls)})：{url.split('/')[-1]}")
            res = fetch_data(url)
            if res:
                all_results.append(res)
                current_batch.append(res)
                
                if len(current_batch) == 3 or i == len(urls) - 1:
                    with display_area:
                        st.divider()
                        cols = st.columns(3)
                        for col_idx, item in enumerate(current_batch):
                            with cols[col_idx]:
                                st.image(item["圖片"], use_container_width=True)
                                st.markdown(f"**{item['名稱']}**")
                                st.markdown(f"""
                                <div class="price-card">
                                    <div class="price-row"><span class="price-label" style="color:#e67e22;">● 美品價格</span><span class="price-val">{item['美品']}</span></div>
                                    <div class="price-row"><span class="price-label" style="color:#3498db;">● PSA10價格</span><span class="price-val">{item['PSA10']}</span></div>
                                    <div class="price-sep"></div>
                                    <div class="price-row"><span class="price-label">● 差額</span><span class="price-val">{item['差額']}</span></div>
                                    <div class="price-row"><span class="price-label">● 比率</span><span class="price-val">{item['比率']}</span></div>
                                </div>
                                """, unsafe_allow_html=True)
                    current_batch = []
            
        status.update(label="✅ 捕捉完畢！", state="complete", expanded=False)
        
        if history_sheet and all_results:
            h_rows = [[now, r["名稱"], r["圖片"], r["PSA10"], r["美品"], r["差額"], r["比率"]] for r in all_results]
            history_sheet.append_rows(h_rows)
else:
    st.info("💡 點擊大師球啟動捕捉。")

st.divider()
st.caption("阿強 TCG Cloud Pro | 2026 終極流式完工版")
