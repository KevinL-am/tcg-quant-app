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

# 1. 頁面設定
st.set_page_config(page_title="TCG Master Quant Pro", page_icon="🔮", layout="wide", initial_sidebar_state="collapsed")

# 2. 終極 CSS (正宗大師球、港幣樣式)
st.markdown("""
    <style>
    [data-testid="stSidebarNav"], section[data-testid="stSidebar"], .stAppDeployButton {display: none;}
    @keyframes flash { 0% { opacity: 0; background-color: #ffffff; } 50% { opacity: 1; background-color: #ffffff; } 100% { opacity: 0; } }
    .flash-effect { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9999; pointer-events: none; animation: flash 0.6s ease-out; }
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 48%, #333 48%, #333 52%, #ffffff 52%) !important;
        color: #ffffff !important; border-radius: 50% !important; width: 200px !important; height: 200px !important;
        border: 10px solid #333 !important; font-size: 110px !important; font-weight: 900 !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.4) !important; transition: all 0.3s ease !important;
        line-height: 1 !important; padding-bottom: 80px !important; position: relative !important;
        z-index: 100 !important; margin: 0 auto !important; display: block !important;
    }
    div.stButton > button:first-child::before, div.stButton > button:first-child::after {
        content: ""; position: absolute; width: 40px; height: 20px; background: #ff004f; top: 22%; border-radius: 50%; z-index: -1;
    }
    div.stButton > button:first-child::before { left: 10px; transform: rotate(-35deg); }
    div.stButton > button:first-child::after { right: 10px; transform: rotate(35deg); }
    .price-card { border: 2px solid #7b2cbf; padding: 15px; border-radius: 15px; background-color: #fcfaff; margin-bottom: 20px; }
    .price-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
    .price-label { font-weight: bold; color: #555; font-size: 13px; }
    .price-val { font-weight: 900; color: #000; font-size: 15px; }
    .hkd-val { font-weight: 900; color: #b8860b; font-size: 15px; }
    </style>
""", unsafe_allow_html=True)

# 3. 換算與連接
def parse_yen(yen_str):
    try:
        num = re.sub(r'[^\d]', '', str(yen_str))
        return float(num) if num else 0
    except: return 0

@st.cache_resource
def connect_gsheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        ss = client.open_by_key("1gGDyFS3Ecq0h45zvVpV72ZimxKvrY-HhNUB4IBLNG4")
        main = ss.sheet1
        try: hist = ss.worksheet("History")
        except: hist = ss.add_worksheet(title="History", rows="1000", cols="20")
        return main, hist
    except Exception as e:
        st.error(f"❌ Google Sheet 連接失敗: {e}")
        return None, None

main_sheet, history_sheet = connect_gsheet()

# 4. 爬蟲 (Playwright)
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")

install_browser()

def fetch_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        page.route("**/*.{png,jpg,jpeg,gif,svg,webp,css,woff,woff2}", lambda route: route.abort())
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_selector("#price-table-body td", timeout=20000)
            soup = BeautifulSoup(page.content(), 'html.parser')
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src and src.startswith('http') else f"https://grading.pokeca-chart.com{src}" if src else "N/A"
            
            p_list = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            tbody = soup.find('tbody', id='price-table-body')
            if tbody:
                tds = tbody.find_all('td')
                if len(tds) >= 4:
                    p_list["美品"], p_list["PSA10"], p_list["差額"], p_list["比率"] = tds[0].text, tds[1].text, tds[2].text, tds[3].text
            return {"名稱": name, "圖片": img_url, **p_list}
        except Exception as e:
            return {"名稱": f"錯誤: {url[-10:]}", "圖片": "N/A", "美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
        finally:
            browser.close()

# 5. UI 與控制
h_col, c_col = st.columns([5, 2])
with h_col: st.title("🛡️ TCG Master Quant Pro")
with c_col:
    with st.popover("⚙️ 控制台", use_container_width=True):
        rate = st.number_input("日元匯率 (JPY/HKD)", value=0.051, format="%.4f")
        pw = st.text_input("密碼", type="password")
        if pw == st.secrets.get("admin_password", "8888") and main_sheet:
            urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
            new_urls = st.text_area("名單:", value="\n".join(urls), height=200)
            if st.button("💾 儲存"):
                main_sheet.clear()
                main_sheet.update('A1', [[u.strip()] for u in new_urls.split("\n") if u.strip()])
                st.rerun()

st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
_, mid, _ = st.columns([1, 1, 1])
with mid:
    run = st.button("M")

# 6. 核心執行
if run:
    if main_sheet:
        urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]
        if not urls:
            st.warning("名單係空嘅。")
        else:
            st.markdown('<div class="flash-effect"></div>', unsafe_allow_html=True)
            results = []
            status = st.status("🔮 捕捉中...", expanded=True)
            
            # 使用分身術捉數
            with ThreadPoolExecutor(max_workers=2) as executor: # 💡 降低 worker 數量提高穩定性
                futures = [executor.submit(fetch_data, url) for url in urls]
                display = st.container()
                batch = []
                for idx, f in enumerate(futures):
                    res = f.result()
                    if res:
                        results.append(res)
                        batch.append(res)
                        status.write(f"捕捉完成 ({idx+1}/{len(urls)})")
                    
                    if len(batch) == 3 or idx == len(urls) - 1:
                        with display:
                            st.divider()
                            cols = st.columns(3)
                            for c_idx, item in enumerate(batch):
                                with cols[c_idx]:
                                    if item["圖片"] != "N/A": st.image(item["圖片"], use_container_width=True)
                                    st.markdown(f"**{item['名稱']}**")
                                    v_b, v_p = parse_yen(item['美品']), parse_yen(item['PSA10'])
                                    st.markdown(f"""
                                    <div class="price-card">
                                        <div class="price-row"><span class="price-label" style="color:#e67e22;">● 美品</span><span class="price-val">{item['美品']}</span></div>
                                        <div class="price-row"><span class="price-label">└ 換算</span><span class="hkd-val">HK$ {v_b*rate:,.0f}</span></div>
                                        <div style="border-top:1px dashed #7b2cbf; margin:8px 0;"></div>
                                        <div class="price-row"><span class="price-label" style="color:#3498db;">● PSA10</span><span class="price-val">{item['PSA10']}</span></div>
                                        <div class="price-row"><span class="price-label">└ 換算</span><span class="hkd-val">HK$ {v_p*rate:,.0f}</span></div>
                                    </div>
                                    """, unsafe_allow_html=True)
                        batch = []
            
            status.update(label="✅ 完成！", state="complete", expanded=False)
            if history_sheet and results:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                h_rows = [[now, r["名稱"], r["圖片"], r["PSA10"], r["美品"], r["差額"], r["比率"]] for r in results]
                history_sheet.append_rows(h_rows)
    else:
        st.error("Sheet 未連接，請檢查 Secrets。")
