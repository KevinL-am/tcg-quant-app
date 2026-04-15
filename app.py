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
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    main_sheet = client.open_by_key(SHEET_ID).sheet1
    try:
        history_sheet = client.open_by_key(SHEET_ID).worksheet("History")
    except:
        history_sheet = None
except Exception as e:
    st.error(f"❌ 雲端連接失敗: {e}")
    st.stop()

# --- 2. 爬蟲核心 (修正版：分開價錢標籤) ---
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
            page.wait_for_timeout(3000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            card_id = url.rstrip('/').split('/')[-1].upper()
            h1_tag = soup.find('h1')
            raw_title = h1_tag.get_text(strip=True) if h1_tag else "未知"
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            
            # 捉圖片
            img_tag = soup.find('main').find('img') or soup.find('img', class_='product-image')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://pokeca-chart.com{src}"
            
            name_ch = GoogleTranslator(source='auto', target='zh-TW').translate(jp_name)
            
            # 💡 修正價錢邏輯：精確定位關鍵字後的數字
            text_blocks = list(soup.stripped_strings)
            def find_price(target_key):
                for i, text in enumerate(text_blocks):
                    if target_key in text:
                        # 喺關鍵字後面搵最近嗰個帶有「円」嘅字
                        for j in range(1, 5):
                            if i + j < len(text_blocks) and "円" in text_blocks[i+j]:
                                return text_blocks[i+j]
                return "N/A"
                
            return {
                "卡片編號": card_id,
                "名稱": name_ch,
                "圖片": img_url,
                "美品価格": find_price("美品価格"), 
                "PSA10価格": find_price("PSA10価格")
            }
        except: return None
        finally: browser.close()

# --- 3. UI 介面 ---
st.title("📊 TCG Quant 精細監控版")

# 讀取 Secrets 密碼
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

# 只有在初次啟動或密碼正確時才讀取一次網址名單 (避免每次互動都重新 API 讀取)
@st.cache_data(ttl=60) # 緩存名單一分鐘
def get_cloud_urls():
    try: return [v for v in main_sheet.col_values(1) if v.startswith("http")]
    except: return []

cloud_urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(cloud_urls), height=200)
    if st.sidebar.button("💾 儲存並同步"):
        urls_to_save = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if urls_to_save: main_sheet.update('A1', urls_to_save)
        st.sidebar.balloons()
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")
    new_urls = "\n".join(cloud_urls)

target_list = [l.strip() for l in new_urls.split("\n") if l.strip()]

# 🚀 只有按下按鈕才會啟動爬蟲，解決「入去自動 Load」問題
if st.button(f"🚀 更新數據並寫入歷史 ({len(target_list)} 張)"):
    if not target_list:
        st.warning("名單係空嘅。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        progress = st.progress(0)
        status_box = st.empty()
        
        for i, url in enumerate(target_list):
            card_id = url.rstrip('/').split('/')[-1]
            status_box.write(f"正在更新: {card_id}")
            data = fetch_card_data(url)
            if data: results.append(data)
            progress.progress((i + 1) / len(target_list))
        
        status_box.empty() # 完成後清除狀態文字
        
        if results:
            # --- 網格大圖顯示 ---
            cols_num = 3
            st.divider()
            grid_cols = st.columns(cols_num)
            
            for i, item in enumerate(results):
                with grid_cols[i % cols_num]:
                    # 1. 圖片 (維持大圖)
                    st.image(item["圖片"], use_container_width=True)
                    
                    # 2. 編號與翻譯名稱 (細字體)
                    st.caption(f"ID: {item['卡片編號']}")
                    st.markdown(f"**{item['名稱']}**")
                    
                    # 3. 價錢顯示 (細字體 + 顏色區分)
                    # 用 Markdown 代替 st.metric，可以精確控制大小
                    st.markdown(f"""
                    <div style="font-size: 14px; border-top: 1px solid #ddd; padding-top: 5px;">
                        <span style="color: #666;">美品:</span> <b>{item['美品価格']}</b><br>
                        <span style="color: #3498db;">PSA10:</span> <b>{item['PSA10価格']}</b>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("") # 撐開一點空間
            
            # 💾 寫入 History
            if history_sheet:
                history_rows = [[now, item["卡片編號"], item["名稱"], f'=IMAGE("{item["圖片"]}")', item["PSA10価格"], item["美品価格"]] for item in results]
                history_sheet.append_rows(history_rows)
                st.toast(f"✅ 歷史數據已存入 Google Sheet！", icon="📉")

st.divider()
st.caption("阿強 Cloud Pro | 精細化 UI 版")
