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

# --- 2. 終極 CSS (包含正宗大師球、閃光特效、HKD 專屬樣式) ---
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

    /* 數據卡片排版 */
    .price-card {
        border: 2px solid #7b2cbf;
        padding: 15px;
        border-radius: 15px;
        background-color: #fcfaff;
        box-shadow: 4px 4px 15px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .price-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 5px;
        width: 100%;
    }
    .price-label { font-weight: bold; color: #555; font-size: 13px; }
    .price-val { font-weight: 900; color: #000; font-size: 15px; text-align: right; }
    .hkd-val { font-weight: 900; color: #b8860b; font-size: 15px; text-align: right; }
    .price-sep { border-top: 1px dashed #7b2cbf; margin: 8px 0; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# 3. 輔助函數：將「12,100円」轉換為數字
def parse_yen(yen_str):
    try:
        if not yen_str or "N/A" in yen_str: return 0
        num_str = re.sub(r'[^\d]', '', yen_str)
        return float(num_str) if num_str else 0
    except:
        return 0

# 4. Google Sheet 連接
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
            return {"名稱": name, "圖片": img_url, **p_list}
        except: return None
        finally: browser.close()

# 6. 頂部導航
head_col, ctrl_col = st.columns([5, 2])
with head_col: st.title("🛡️ TCG Master Quant Pro")

with ctrl_col:
    # 💡 新功能：控制台內加埋匯率設定
    with st.popover("⚙️ 控制台", use_container_width=True):
        st.write("### 📊 系統設定")
        rate = st.number_input("今日日元匯率 (JPY/HKD)", value=0.051, format="%.4f")
        st.write("---")
        pw = st.text_input("管理授權碼", type="password")
        if main_sheet and pw == st.secrets.get("admin_password", "8888"):
            urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
            new_urls = st.text_area("監控名單:", value="\n".join(urls), height=200)
            if st.button("💾 儲存並同步"):
                main_sheet.clear()
                main_sheet.update('A1', [[u.strip()] for u in new_urls.split("\n") if u.strip()])
                st.cache_data.clear()
                st.rerun()

# 7. 主介面
st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
_, ball_mid, _ = st.columns([1, 1, 1])
with ball_mid:
    start_capture = st.button("M", key="master_ball_final")

# 8. 核心加載 (分身術 + 港幣計算)
if start_capture:
    urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
    if not urls:
        st.warning("名單內無網址。")
    else:
        st.markdown('<div class="flash-effect"></div>', unsafe_allow_html=True)
        all_results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        status = st.status("🚀 大師球極速捕捉中...", expanded=True)
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(fetch_data, url): url for url in urls}
            display_area = st.container()
            current_batch = []
            count = 0

            for future in future_to_url:
                count += 1
                res = future.result()
                if res:
                    all_results.append(res)
                    current_batch.append(res)
                
                if len(current_batch) == 3 or count == len(urls):
                    with display_area:
                        st.divider()
                        cols = st.columns(3)
                        for col_idx, item in enumerate(current_batch):
                            # 計算港幣
                            val_bihin = parse_yen(item['美品'])
                            val_psa10 = parse_yen(item['PSA10'])
                            hkd_bihin = f"HK$ {val_bihin * rate:,.0f}"
                            hkd_psa10 = f"HK$ {val_psa10 * rate:,.0f}"
                            
                            with cols[col_idx]:
                                st.image(item["圖片"], use_container_width=True)
                                st.markdown(f"**{item['名稱']}**")
                                st.markdown(f"""
                                <div class="price-card">
                                    <div class="price-row"><span class="price-label" style="color:#e67e22;">● 美品</span><span class="price-val">{item['美品']}</span></div>
                                    <div class="price-row"><span class="price-label">└ 換算港幣</span><span class="hkd-val">{hkd_bihin}</span></div>
                                    <div class="price-sep"></div>
                                    <div class="price-row"><span class="price-label" style="color:#3498db;">● PSA10</span><span class="price-val">{item['PSA10']}</span></div>
                                    <div class="price-row"><span class="price-label">└ 換算港幣</span><span class="hkd-val">{hkd_psa10}</span></div>
                                    <div class="price-sep"></div>
                                    <div class="price-row"><span class="price-label">● 差額</span><span class="price-val">{item['差額']}</span></div>
                                    <div class="price-row"><span class="price-label">● 比率</span><span class="price-val">{item['比率']}</span></div>
                                </div>
                                """, unsafe_allow_html=True)
                    current_batch = []
            
        status.update(label="✅ 全體收服完成！數據已更新。", state="complete", expanded=False)
        
        if history_sheet and all_results:
            h_rows = [[now, r["名稱"], r["圖片"], r["PSA10"], r["美品"], r["差額"], r["比率"]] for r in all_results]
            history_sheet.append_rows(h_rows)
else:
    st.info("💡 準備就緒。點擊大師球啟動「分身術」極速捕捉。")

st.divider()
st.caption("阿強 TCG Cloud Pro | 2026 匯率換算極速版")
