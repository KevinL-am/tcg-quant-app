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
    
    # 你的 Sheet ID
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

# --- 2. 爬蟲核心 (保持不變) ---
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
            
            # 捉卡片編號
            card_id = url.rstrip('/').split('/')[-1].upper()
            
            # 捉日文原名
            h1_tag = soup.find('h1')
            raw_title = h1_tag.get_text(strip=True) if h1_tag else "未知"
            # 剷走價錢推移等字眼，淨低個名
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            
            # 捉卡片圖片
            img_tag = soup.find('main').find('img') or soup.find('img', class_='product-image') or soup.find('h1').find_previous('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    # 處理相對路徑，變返做完整網址
                    base_url = "https://pokeca-chart.com"
                    img_url = src if src.startswith('http') else f"{base_url}{src}"
            
            # 捉翻譯名稱
            name_ch = GoogleTranslator(source='auto', target='zh-TW').translate(jp_name)
            
            # 捉價錢
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
                "圖片": img_url,
                "美品価格": find_v("美品価格", "円"), 
                "PSA10価格": find_v("PSA10価格", "円")
            }
        except Exception as e: 
            st.error(f"捉取失敗 ({url}): {e}")
            return None
        finally: 
            browser.close()

# --- 3. UI 介面 ---
st.title("📊 阿強 TCG Quant 大圖網格版")

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
    st.sidebar.success("✅ 已解鎖")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(cloud_urls), height=300)
    if st.sidebar.button("💾 儲存並同步"):
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
            # 💾 寫入 Google Sheet 歷史分頁 (保持不變)
            if history_sheet:
                history_rows = []
                for item in results:
                    # 圖片網址要轉換成 Google Sheet 嘅 IMAGE 公式
                    img_formula = f'=IMAGE("{item["圖片"]}")' if item["圖片"] != "N/A" else "N/A"
                    history_rows.append([now, item["卡片編號"], item["名稱"], img_formula, item["PSA10価格"], item["美品価格"]])
                
                # 追加到底部
                history_sheet.append_rows(history_rows)
                st.success(f"✅ 數據已存入 Google Sheet 'History' 分頁！(包含圖片公式)")

            st.divider()
            
            # --- Streamlit 大圖網格顯示 (NEW!) ---
            # 定義每行顯示幾多張卡 (例如: 3 欄)
            cols_num = 3
            # 創建欄位
            cols = st.columns(cols_num)
            
            # 迴圈處理結果，以網格方式顯示
            for i, item in enumerate(results):
                # 計算依家係第幾欄
                col_index = i % cols_num
                # 使用特定的欄位嚟渲染內容
                with cols[col_index]:
                    # 卡片容器
                    st.divider() # 欄內的分隔線
                    
                    # 標題：卡片 ID
                    st.subheader(f"🆔 {item['卡片編號']}")
                    # 子標題：名稱
                    st.write(f"🏷️ **{item['名稱']}**")
                    
                    # 圖片顯示：大大張，並設定 `use_container_width=True`，令佢填滿個欄位
                    if item["圖片"] != "N/A":
                        st.image(item["圖片"], caption=item["名稱"], use_container_width=True)
                    else:
                        st.warning("❌ 搵唔到圖片")
                    
                    # 價錢詳情
                    # st.divider() # 欄內的分隔線，可選
                    price_col1, price_col2 = st.columns(2)
                    price_col1.metric(label="🌟 美品価格", value=item["美品価格"])
                    price_col2.metric(label="💎 PSA10価格", value=item["PSA10価格"])
                    st.divider() # 卡片之間的分隔線

st.divider()
st.caption("阿強 Cloud Pro | 大圖網格紀錄系統")
