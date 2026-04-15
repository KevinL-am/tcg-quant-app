import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from datetime import datetime

st.set_page_config(page_title="TCG Master Ball Pro", page_icon="🔮", layout="wide")

# --- 1. 終極大師球 造型 CSS ---
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background: linear-gradient(#7b2cbf 50%, #ffffff 50%);
        color: #ffffff;
        border-radius: 50%;
        width: 160px;
        height: 160px;
        border: 10px solid #333;
        font-size: 80px !important;
        font-weight: 900;
        box-shadow: 0 10px 20px rgba(0,0,0,0.5);
        display: block;
        margin: 10px auto;
        transition: all 0.2s ease;
        line-height: 0.1;
        padding-bottom: 70px;
        position: relative;
    }
    div.stButton > button:first-child:hover { transform: scale(1.05); }
    .master-label { text-align: center; font-weight: 900; color: #7b2cbf; font-size: 20px; margin-top: -5px; margin-bottom: 20px;}
    
    /* 數據框樣式：確保唔會爆開 */
    .price-box {
        font-size: 14px; 
        border: 2px solid #7b2cbf; 
        padding: 15px; 
        border-radius: 12px; 
        background-color: #fcfaff; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .row { display: flex; justify-content: space-between; margin-bottom: 8px; align-items: center; }
    .label { font-weight: bold; color: #555; }
    .val { font-weight: 900; color: #000; text-align: right; }
    .divider { border-top: 1px dashed #7b2cbf; margin: 10px 0; }
    </style>
""", unsafe_allow_html=True)

# --- 2. Google Sheet 連接 ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    spreadsheet = client.open_by_key(SHEET_ID)
    main_sheet = spreadsheet.sheet1
    
    # 自動檢查並建立 History 頁
    try:
        history_sheet = spreadsheet.worksheet("History")
    except:
        # 如果搵唔到就自動開一個
        history_sheet = spreadsheet.add_worksheet(title="History", rows="1000", cols="20")
        history_sheet.append_row(["更新時間", "名稱", "圖片", "PSA10價格", "美品價格", "差額", "比率"])
except Exception as e:
    st.error(f"❌ Google Sheet 連接失敗: {e}")
    st.stop()

# --- 3. 爬蟲核心 (對準價格數據) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_master_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # 等候表格入面嘅「円」字出現
            page.wait_for_selector("td:has-text('円')", timeout=20000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"

            data = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            # 直接搵 tbody 入面嘅數據
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
st.sidebar.title("⚙️ 大師球控制台")
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("🔑 管理員密碼", type="password")

# 讀取現有名單
urls = [v for v in main_sheet.col_values(1) if v.startswith("http")]

if pw == REAL_PW:
    st.sidebar.success("✅ 身分已確認")
    new_urls = st.sidebar.text_area("🔧 編輯監控名單 (每行一條 Link):", value="\n".join(urls), height=300)
    if st.sidebar.button("💾 儲存並更新名單"):
        rows_to_save = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if rows_to_save: main_sheet.update('A1', rows_to_save)
        st.cache_data.clear()
        st.rerun()
else:
    st.sidebar.info("💡 密碼正確後可編輯名單。")

# --- 5. 主介面 ---
st.title("🛡️ TCG Master Ball Quant Pro")

col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    update_btn = st.button("M")
    st.markdown('<p class="master-label">MASTER BALL UPDATE</p>', unsafe_allow_html=True)

if update_btn:
    if not urls:
        st.warning("名單係空嘅，請喺側欄加入網址。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        bar = st.progress(0)
        status = st.empty()
        
        for i, url in enumerate(urls):
            status.write(f"🔮 正在捕捉數據 ({i+1}/{len(urls)})...")
            res = fetch_master_data(url)
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
                    st.markdown(f"<p style='font-weight:bold; margin-bottom:5px;'>{item['名稱']}</p>", unsafe_allow_html=True)
                    # 💡 重新排版嘅數據框
                    st.markdown(f"""
                    <div class="price-box">
                        <div class="row"><span class="label" style="color:#e67e22;">● 美品價格</span><span class="val">{item['美品']}</span></div>
                        <div class="row"><span class="label" style="color:#3498db;">● PSA10價格</span><span class="val">{item['PSA10']}</span></div>
                        <div class="divider"></div>
                        <div class="row"><span class="label">● 差額</span><span class="val">{item['差額']}</span></div>
                        <div class="row"><span class="label">● 比率</span><span class="val">{item['比率']}</span></div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("")
            st.balloons()
else:
    st.info("💡 準備就緒。點擊上方「大師球」開始獲取最新價格。")

st.divider()
st.caption("阿強 TCG Cloud Pro | 2026 旗艦版")
