import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from datetime import datetime
from deep_translator import GoogleTranslator

st.set_page_config(page_title="TCG Quant Pro", page_icon="📈", layout="wide")

# --- 1. 連接 Google Sheets ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    # 讀取 Streamlit Secrets 嘅門卡
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # 呢個就係你張 Sheet 嘅 ID
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    
    # 開啟名單頁同歷史頁
    main_sheet = client.open_by_key(SHEET_ID).sheet1
    try:
        history_sheet = client.open_by_key(SHEET_ID).worksheet("History")
    except:
        history_sheet = None # 萬一冇 History 頁都唔會 Crash
except Exception as e:
    st.error(f"❌ 雲端連接失敗: {e}")
    st.stop()

# --- 2. 爬蟲核心 ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            raw_title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "未知"
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            name_ch = GoogleTranslator(source='auto', target='zh-TW').translate(jp_name)
            
            text_blocks = list(soup.stripped_strings)
            def find_v(keyword, unit):
                for i, text in enumerate(text_blocks):
                    if keyword in text:
                        for j in range(1, 10):
                            if i + j < len(text_blocks) and unit in text_blocks[i+j]: return text_blocks[i+j]
                return "N/A"
                
            return {
                "卡片編號": url.rstrip('/').split('/')[-1].upper(), 
                "名稱": name_ch, 
                "美品価格": find_v("美品価格", "円"), 
                "PSA10価格": find_v("PSA10価格", "円")
            }
        except: 
            return None
        finally: 
            browser.close()

# --- 3. UI 介面 ---
st.title("📊 阿強 TCG Quant 歷史紀錄版")

# 讀取 Secrets 密碼，冇設就用 8888
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

# 讀取雲端名單
def get_cloud_urls():
    try:
        return [v for v in main_sheet.col_values(1) if v.startswith("http")]
    except:
        return []

cloud_urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 身分已確認")
    new_urls = st.sidebar.text_area("🔧 編輯監控名單 (每行一條 Link):", value="\n".join(cloud_urls), height=300)
    if st.sidebar.button("💾 儲存名單至雲端"):
        urls_to_save = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if urls_to_save: 
            main_sheet.update('A1', urls_to_save)
        st.sidebar.balloons()
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式。請輸入正確密碼以編輯。")
    new_urls = "\n".join(cloud_urls)

target_list = [l.strip() for l in new_urls.split("\n") if l.strip()]

if st.button(f"🚀 更新數據並寫入歷史 ({len(target_list)} 張)"):
    if not target_list:
        st.warning("名單係空嘅，請先入密碼加 Link。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        progress = st.progress(0)
        
        for i, url in enumerate(target_list):
            st.write(f"正在更新: {url.split('/')[-2]}")
            data = fetch_card_data(url)
            if data: 
                results.append(data)
            progress.progress((i + 1) / len(target_list))
        
        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            
            # 💾 寫入 History 分頁
            if history_sheet:
                history_rows = [[now, item["卡片編號"], item["名稱"], item["PSA10価格"], item["美品価格"]] for item in results]
                history_sheet.append_rows(history_rows)
                st.success(f"✅ 歷史數據已同步至 Google Sheet 'History' 分頁！")

st.divider()
st.caption("阿強 Cloud Pro | 24小時歷史監控系統")
