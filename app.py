import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
from datetime import datetime

st.set_page_config(page_title="TCG Quant Ultra", page_icon="💎", layout="wide")

# --- 1. 連接 Google Sheets ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # 使用大佬原本的 SHEET_ID
    SHEET_ID = "1wOxuP_GtaKQpYArGHgVehkR61SwQIywz_9WRSQFwmUM"
    main_sheet = client.open_by_key(SHEET_ID).sheet1
    try:
        history_sheet = client.open_by_key(SHEET_ID).worksheet("History")
    except:
        history_sheet = None
except Exception as e:
    st.error(f"❌ 雲端連接失敗: {e}")
    st.stop()

# --- 2. 爬蟲核心 (四數據精準定位) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000) # 畀足時間加載動態數據
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. 捉名稱 (日文原名)
            h1_tag = soup.find('h1')
            full_name = h1_tag.get_text(strip=True) if h1_tag else "未知"
            # 簡單處理名稱，攞「の」字前面嘅部分
            jp_name = full_name.split('の')[0] if 'の' in full_name else full_name
            
            # 2. 捉圖片
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img') or soup.find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            # 3. 捉表格數據 (美品, PSA10, 差額, 比率)
            scraped = {"bihin": "N/A", "psa10": "N/A", "diff": "N/A", "ratio": "N/A"}
            rows = soup.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    label = th.get_text(strip=True)
                    val = td.get_text(strip=True)
                    if "美品価格" in label: scraped["bihin"] = val
                    elif "PSA10価格" in label: scraped["psa10"] = val
                    elif "差額" in label: scraped["diff"] = val
                    elif "比率" in label: scraped["ratio"] = val
            
            return {
                "名稱": jp_name, 
                "圖片": img_url,
                "美品": scraped["bihin"], 
                "PSA10": scraped["psa10"], 
                "差額": scraped["diff"], 
                "比率": scraped["ratio"]
            }
        except:
            return None
        finally:
            browser.close()

# --- 3. UI 與自動化任務 ---
st.title("📊 TCG Quant 全自動大圖版")

# 側欄
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

@st.cache_data(ttl=600)
def get_cloud_urls():
    try:
        return [v for v in main_sheet.col_values(1) if v.startswith("http")]
    except:
        return []

urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖管理員權限")
    new_urls_input = st.sidebar.text_area("🔧 編輯監控名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存名單並刷新"):
        rows_to_update = [[u.strip()] for u in new_urls_input.split("\n") if u.strip()]
        main_sheet.clear()
        if rows_to_update:
            main_sheet.update('A1', rows_to_update)
        st.cache_data.clear() 
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")

# --- 🚀 自動 Load 邏輯 ---
if not urls:
    st.info("👈 請喺側欄輸入 Pokeca-chart 網址名單。")
else:
    # 每一小時自動爬一次，或者儲存名單時強制重爬
    @st.cache_data(ttl=3600)
    def auto_run_fetch(url_list):
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for url in url_list:
            data = fetch_card_data(url)
            if data:
                results.append(data)
        
        # 同步到 Google Sheet History
        if history_sheet and results:
            history_rows = [[now, i["名稱"], f'=IMAGE("{i["圖片"]}")', i["PSA10"], i["美品"], i["差額"], i["比率"]] for i in results]
            history_sheet.append_rows(history_rows)
        return results, now

    st.write("🔄 **正在同步最新價格...** (請稍候 10-20 秒)")
    final_data, last_update_ts = auto_run_fetch(urls)

    if final_data:
        st.success(f"✅ 更新完成 (最後更新: {last_update_ts})")
        
        # 顯示大圖網格
        cols = st.columns(3)
        for index, item in enumerate(final_data):
            with cols[index % 3]:
                # 1. 顯示大圖
                st.image(item["圖片"], use_container_width=True)
                
                # 2. 顯示名稱 (唔再要重複嘅 ID 行)
                st.markdown(f"**{item['名稱']}**")
                
                # 3. 四數據美化顯示框 (修正咗 f-string 語法)
                html_code = f"""
                <div style="font-size: 14px; border: 1px solid #eee; padding: 12px; border-radius: 8px; background-color: #ffffff; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="color: #e67e22; font-weight: bold;">● 美品：</span><b>{item['美品']}</b>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="color: #3498db; font-weight: bold;">● PSA10：</span><b>{item['PSA10']}</b>
                    </div>
                    <div style="border-top: 1px dashed #ddd; margin-top: 8px; padding-top: 8px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                            <span style="color: #666;">● 差額：</span><b>{item['差額']}</b>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #666;">● 比率：</span><b>{item['比率']}</b>
                        </div>
                    </div>
                </div>
                """
                st.markdown(html_code, unsafe_allow_html=True)
                st.write("")

st.divider()
st.caption("阿強 Cloud Pro | 全自動數據系統")
