import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from deep_translator import GoogleTranslator

# 網頁設定
st.set_page_config(page_title="TCG Quant Pro", page_icon="📈", layout="wide")

# --- 1. 連接 Google Sheets ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

try:
    # 從 Streamlit Secrets 讀取門卡
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)

    # ⚠️ 大佬！請喺下面引號入面貼入你張 Google Sheet 嗰串 ID ⚠️
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM" 
    
    sheet = client.open_by_key(SHEET_ID).sheet1
except Exception as e:
    st.error(f"❌ 雲端連接失敗 (請檢查 Secrets 同埋 Sheet 共用權限): {e}")
    st.stop()

# --- 2. 爬蟲環境 ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            raw_title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "未知卡片"
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            # 自動翻譯做繁體中文
            name_ch = GoogleTranslator(source='auto', target='zh-TW').translate(jp_name)
            
            text_blocks = list(soup.stripped_strings)
            def find_v(keyword, unit):
                for i, text in enumerate(text_blocks):
                    if keyword in text:
                        for j in range(1, 10):
                            if i + j < len(text_blocks) and unit in text_blocks[i+j]: return text_blocks[i+j]
                return "N/A"
            return {"卡片編號": url.rstrip('/').split('/')[-1].upper(), "名稱": name_ch, "美品価格": find_v("美品価格", "円"), "PSA10価格": find_v("PSA10価格", "円"), "溢價比率": find_v("比率", "%")}
        except: return None
        finally: browser.close()

# --- 3. UI 介面 ---
st.title("📊 阿強 TCG Quant 終極版")

# 密碼解鎖
pw = st.sidebar.text_input("管理員密碼", type="password")

# 從雲端攞名單
def get_urls():
    try: return [v for v in sheet.col_values(1) if v.startswith("http")]
    except: return []

cloud_urls = get_urls()

if pw == "8888":
    st.sidebar.success("✅ 已解鎖")
    new_urls = st.sidebar.text_area("🔧 編輯監控名單:", value="\n".join(cloud_urls), height=300)
    if st.sidebar.button("💾 儲存並同步到雲端"):
        urls_to_save = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        sheet.clear()
        if urls_to_save: sheet.update('A1', urls_to_save)
        st.sidebar.balloons()
        st.rerun()
else:
    st.sidebar.info("唯讀模式 (密碼: 8888)")
    new_urls = "\n".join(cloud_urls)

target_list = [l.strip() for l in new_urls.split("\n") if l.strip()]

if st.button(f"🚀 批次更新雲端名單 ({len(target_list)} 張)"):
    if not target_list:
        st.warning("名單係空嘅，請先入密碼加 Link。")
    else:
        results = []
        progress = st.progress(0)
        for i, url in enumerate(target_list):
            st.write(f"正在更新: {url.split('/')[-2]}")
            data = fetch_card_data(url)
            if data: results.append(data)
            progress.progress((i + 1) / len(target_list))
        if results: st.dataframe(pd.DataFrame(results), use_container_width=True)

st.divider()
st.caption("阿強 TCG Cloud Pro | 數據永久存儲於 Google Sheets")
