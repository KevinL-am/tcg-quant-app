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

# --- 2. 爬蟲核心 (深度定位版) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # 加入 User-Agent 模擬真人，防止被擋
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"})
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000) # 畀多 1 秒等數據載入
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. 捉卡片編號
            card_id = url.rstrip('/').split('/')[-1].upper()
            
            # 2. 捉日文名稱
            h1_tag = soup.find('h1')
            jp_name = h1_tag.get_text(strip=True) if h1_tag else "未知"
            jp_name = jp_name.split('の')[0] if 'の' in jp_name else jp_name
            
            # 3. 捉圖片
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img') or soup.find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            # 4. 💡 深度搜索：掃瞄所有表格行
            bihin = "N/A"
            psa10 = "N/A"
            
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    header_text = cells[0].get_text(strip=True)
                    value_text = cells[1].get_text(strip=True)
                    
                    if "美品価格" in header_text:
                        bihin = value_text
                    elif "PSA10価格" in header_text:
                        psa10 = value_text
            
            # 如果表格搵唔到，試吓喺全網頁搵關鍵字
            if bihin == "N/A" or psa10 == "N/A":
                all_text = list(soup.stripped_strings)
                for i, text in enumerate(all_text):
                    if "美品価格" in text and bihin == "N/A":
                        if i+1 < len(all_text) and "円" in all_text[i+1]: bihin = all_text[i+1]
                    if "PSA10価格" in text and psa10 == "N/A":
                        if i+1 < len(all_text) and "円" in all_text[i+1]: psa10 = all_text[i+1]
                
            return {
                "卡片編號": card_id,
                "名稱": jp_name,
                "圖片": img_url,
                "美品価格": bihin, 
                "PSA10価格": psa10
            }
        except: return None
        finally: browser.close()

# --- 3. UI 與全自動邏輯 ---
st.title("📊 TCG Quant 全自動大圖版")

# 密碼與名單管理 (擺側欄)
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

@st.cache_data(ttl=600) # 每 10 分鐘檢查一次名單變動
def get_cloud_urls():
    return [v for v in main_sheet.col_values(1) if v.startswith("http")]

urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖")
    new_urls_input = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存並強制同步"):
        rows = [[u.strip()] for u in new_urls_input.split("\n") if u.strip()]
        main_sheet.clear()
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear() # 關鍵：清空緩存，強制重新爬蟲
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")

# --- 🚀 自動更新任務 ---
if not urls:
    st.info("👈 請喺側欄輸入 Pokeca-chart 網址名單。")
else:
    # ttl 設定為 3600 (一小時更新一次)，若要即時更新，撳側欄個「儲存並強制同步」掣
    @st.cache_data(ttl=3600)
    def auto_run(url_list):
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for url in url_list:
            data = fetch_card_data(url)
            if data: results.append(data)
        
        if history_sheet and results:
            history_rows = [[now, item["卡片編號"], item["名稱"], f'=IMAGE("{item["圖片"]}")', item["PSA10価格"], item["美品価格"]] for item in results]
            history_sheet.append_rows(history_rows)
        return results, now

    st.write("🔄 **正在檢查最新價格...** (請稍候約 10-20 秒)")
    final_data, last_ts = auto_run(urls)

    if final_data:
        st.success(f"✅ 數據已自動更新至最新 (更新時間: {last_ts})")
        
        # 顯示網格
        grid = st.columns(3)
        for i, item in enumerate(final_data):
            with grid[i % 3]:
                st.image(item["圖片"], use_container_width=True)
                st.markdown(f"**{item['名稱']}**")
                st.caption(f"ID: {item['卡片編號']}")
                
                # 美化價錢顯示
                st.markdown(f"""
                <div style="font-size: 15px; border-top: 1px solid #eee; padding-top: 8px; color: #333;">
                    <span style="color: #e67e22; font-weight: bold;">美品：</span> <b>{item['美品価格']}</b><br>
                    <span style="color: #3498db; font-weight: bold;">PSA10：</span> <b>{item['PSA10価格']}</b>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

st.divider()
st.caption("阿強 Cloud Pro | 24H 全自動數據抓取")
