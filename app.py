import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from datetime import datetime

st.set_page_config(page_title="TCG Quant Auto", page_icon="🤖", layout="wide")

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

# --- 2. 爬蟲核心 (適應新 grading 域名) ---
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
            
            # 捉卡片編號
            card_id = url.rstrip('/').split('/')[-1].upper()
            
            # 捉日文名稱 (唔再翻譯)
            h1_tag = soup.find('h1')
            jp_name = h1_tag.get_text(strip=True) if h1_tag else "未知"
            # 清理標題
            jp_name = jp_name.split('の')[0] if 'の' in jp_name else jp_name
            
            # 捉圖片 (針對 grading 域名優化)
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            # 💡 針對 Table 結構精確抓取
            def get_table_price(label):
                # 搵包含該標籤嘅 th，然後攞佢隔離個 td
                target_th = soup.find('th', string=lambda s: s and label in s)
                if target_th:
                    td = target_th.find_next_sibling('td')
                    if td: return td.get_text(strip=True)
                return "N/A"

            bihin = get_table_price("美品価格")
            psa10 = get_table_price("PSA10価格")
                
            return {
                "卡片編號": card_id,
                "名稱": jp_name,
                "圖片": img_url,
                "美品価格": bihin, 
                "PSA10価格": psa10
            }
        except: return None
        finally: browser.close()

# --- 3. 處理邏輯與 UI ---
st.title("📊 TCG Quant 全自動監控版")

# 密碼驗證
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

# 讀取名單
@st.cache_data(ttl=300) # 緩存名單 5 分鐘，避免頻繁讀取 Sheet
def get_cloud_urls():
    return [v for v in main_sheet.col_values(1) if v.startswith("http")]

urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖")
    new_urls_input = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存並強制更新"):
        # 寫入 Sheet
        rows_to_update = [[u.strip()] for u in new_urls_input.split("\n") if u.strip()]
        main_sheet.clear()
        if rows_to_update: main_sheet.update('A1', rows_to_update)
        st.cache_data.clear() # 清除緩存
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")

# --- 🚀 自動化執行部分 ---
if not urls:
    st.info("請喺左邊編輯名單加入網址。")
else:
    # 使用 cache 確保唔會每次郁吓側欄都重新爬蟲，設定 1 小時 (3600秒) 更新一次，或手動重新整理網頁更新
    @st.cache_data(ttl=3600)
    def auto_update_task(url_list):
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for url in url_list:
            data = fetch_card_data(url)
            if data: results.append(data)
        
        # 自動寫入 Google Sheet 歷史紀錄
        if history_sheet and results:
            history_rows = [[now, item["卡片編號"], item["名稱"], f'=IMAGE("{item["圖片"]}")', item["PSA10価格"], item["美品価格"]] for item in results]
            history_sheet.append_rows(history_rows)
            
        return results, now

    st.write("🔄 **正在自動同步最新數據...**")
    final_data, last_update = auto_update_task(urls)
    
    # 顯示結果
    if final_data:
        st.success(f"✅ 更新完成 (最後更新時間: {last_update})")
        grid = st.columns(3)
        for i, item in enumerate(final_data):
            with grid[i % 3]:
                st.image(item["圖片"], use_container_width=True)
                st.markdown(f"**{item['名稱']}**")
                st.caption(f"ID: {item['卡片編號']}")
                st.markdown(f"""
                <div style="font-size: 15px; border-top: 1px solid #eee; padding-top: 8px;">
                    <span style="color: #e67e22; font-weight: bold;">美品：</span> <b>{item['美品価格']}</b><br>
                    <span style="color: #3498db; font-weight: bold;">PSA10：</span> <b>{item['PSA10価格']}</b>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

st.divider()
st.caption("阿強 Cloud Pro | 全自動爬蟲模式")
