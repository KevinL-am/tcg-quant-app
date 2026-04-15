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
    # 讀取 Secrets 門卡
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    
    # 你張 Sheet 嘅 ID
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    
    # 開啟工作表
    main_sheet = client.open_by_key(SHEET_ID).sheet1
    try:
        history_sheet = client.open_by_key(SHEET_ID).worksheet("History")
    except:
        history_sheet = None
except Exception as e:
    st.error(f"❌ 雲端連接失敗: {e}")
    st.stop()

# --- 2. 爬蟲核心 (加強版：捉圖) ---
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
            
            # --- 捉卡片編號 (例如: sv4a-331-001) ---
            # 從 URL 末端提取編號
            card_id = url.rstrip('/').split('/')[-1].upper()
            
            # --- 捉日文原名 ---
            h1_tag = soup.find('h1')
            raw_title = h1_tag.get_text(strip=True) if h1_tag else "未知"
            # 剷走價錢推移等字眼，淨低個名
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            
            # --- 捉卡片圖片 (NEW!) ---
            # 搵 h1 附近嘅第一幅圖，通常就係卡樣
            img_tag = soup.find('main').find('img') or soup.find('img', class_='product-image') or soup.find('h1').find_previous('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    # 處理相對路徑，變返做完整網址
                    base_url = "https://pokeca-chart.com"
                    img_url = src if src.startswith('http') else f"{base_url}{src}"
            
            # --- 捉翻譯名稱 ---
            name_ch = GoogleTranslator(source='auto', target='zh-TW').translate(jp_name)
            
            # --- 捉價錢 ---
            text_blocks = list(soup.stripped_strings)
            def find_v(keyword, unit):
                for i, text in enumerate(text_blocks):
                    if keyword in text:
                        for j in range(1, 10):
                            if i + j < len(text_blocks) and unit in text_blocks[i+j]: return text_blocks[i+j]
                return "N/A"
                
            return {
                "卡片編號": card_id,
                "名稱": name_ch,
                "圖片": img_url,  # 儲存圖片網址
                "美品価格": find_v("美品価格", "円"), 
                "PSA10価格": find_v("PSA10価格", "円")
            }
        except Exception as e: 
            st.error(f"捉取失敗 ({url}): {e}")
            return None
        finally: 
            browser.close()

# --- 3. UI 介面 ---
st.title("📊 阿強 TCG Quant 神卡紀錄版")

# Secrets 密碼驗證
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

# 從雲端攞名單
def get_cloud_urls():
    try:
        return [v for v in main_sheet.col_values(1) if v.startswith("http")]
    except:
        return []

cloud_urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 身分已確認")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(cloud_urls), height=300)
    if st.sidebar.button("💾 儲存名單"):
        urls_to_save = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if urls_to_save: main_sheet.update('A1', urls_to_save)
        st.sidebar.balloons()
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式。請輸入密碼解鎖。")
    new_urls = "\n".join(cloud_urls)

target_list = [l.strip() for l in new_urls.split("\n") if l.strip()]

if st.button(f"🚀 更新數據並寫入歷史 ({len(target_list)} 張)"):
    if not target_list:
        st.warning("名單係空嘅。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        progress = st.progress(0)
        
        # 開一個顯示位置
        status_box = st.empty()
        
        for i, url in enumerate(target_list):
            card_id = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
            status_box.write(f"正在更新: {card_id}")
            data = fetch_card_data(url)
            if data: 
                results.append(data)
            progress.progress((i + 1) / len(target_list))
        
        status_box.write("✅ 更新完成！正在整理數據...")
        
        if results:
            df = pd.DataFrame(results)
            
            # --- Streamlit 表格顯示圖片 (NEW!) ---
            # 重新整理欄位順序，將編號擺第一，圖片擺最前
            cols = ["卡片編號", "名稱", "圖片", "美品価格", "PSA10価格"]
            df = df[cols]
            
            # 使用 st.dataframe 並設定 column_config 嚟顯示圖片
            st.dataframe(df, use_container_width=True, column_config={
                "卡片編號": st.column_config.TextColumn("卡片編號"),
                "名稱": st.column_config.TextColumn("翻譯名稱"),
                "圖片": st.column_config.ImageColumn("圖片", help="卡片圖片"),
                "美品価格": st.column_config.TextColumn("美品價"),
                "PSA10価格": st.column_config.TextColumn("PSA 10 價")
            })
            
            # 💾 寫入 Google Sheet 歷史分頁 (加強版：寫入圖片公式) (NEW!)
            if history_sheet:
                history_rows = []
                for item in results:
                    # 圖片網址要轉換成 Google Sheet 嘅 IMAGE 公式
                    img_url_ GS_IMAGE_FORMULA = f'=IMAGE("{item["圖片"]}")' if item["圖片"] != "N/A" else "N/A"
                    
                    history_rows.append([now, item["卡片編號"], item["名稱"], GS_IMAGE_FORMULA, item["PSA10価格"], item["美品価格"]])
                
                # 批量追加到 History 頁面最底部
                history_sheet.append_rows(history_rows)
                st.success(f"✅ 歷史數據已同步至 Google Sheet 'History' 分頁！(已包含圖片)")

st.divider()
st.caption("阿強 Cloud Pro | 神卡圖片追蹤系統")
