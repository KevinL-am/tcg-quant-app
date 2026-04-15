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
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000) # 畀足時間等數據出嚟
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. 捉名稱 (日文原名)
            h1_tag = soup.find('h1')
            jp_name = h1_tag.get_text(strip=True).split('の')[0] if h1_tag else "未知"
            
            # 2. 捉圖片
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img') or soup.find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                if src:
                    img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            # 3. 捉表格數據 (美品, PSA10, 差額, 比率)
            data = {"bihin": "N/A", "psa10": "N/A", "diff": "N/A", "ratio": "N/A"}
            rows = soup.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    label = th.get_text(strip=True)
                    value = td.get_text(strip=True)
                    if "美品価格" in label: data["bihin"] = value
                    elif "PSA10価格" in label: data["psa10"] = value
                    elif "差額" in label: data["diff"] = value
                    elif "比率" in label: data["ratio"] = value
            
            return {
                "名稱": jp_name, "圖片": img_url,
                "美品": data["bihin"], "PSA10": data["psa10"], 
                "差額": data["diff"], "比率": data["ratio"]
            }
        except: return None
        finally: browser.close()

# --- 3. UI 介面與自動化 ---
st.title("📊 TCG Quant 全自動大圖版")

# 側欄管理
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
    st.sidebar.success("✅ 身分已確認")
    new_urls_area = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存並強制刷新"):
        rows = [[u.strip()] for u in new_urls_area.split("\n") if u.strip()]
        main_sheet.clear()
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear() 
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")

# --- 🚀 全自動更新邏輯 ---
if not urls:
    st.info("👈 請喺側欄名單輸入 Pokeca-chart 網址。")
else:
    # 緩存 1 小時，避免頻繁爬蟲；想即時更新就用側欄個儲存掣
    @st.cache_data(ttl=3600)
    def auto_fetch_all(url_list):
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for url in url_list:
            res = fetch_card_data(url)
            if res: results.append(res)
        
        # 同步到 Google Sheet 歷史紀錄
        if history_sheet and results:
            history_rows = [[now, i["名稱"], f'=IMAGE("{i["圖片"]}")', i["PSA10"], i["美品"], i["差額"], i["比率"]] for i in results]
            history_sheet.append_rows(history_rows)
        return results, now

    st.write("🔄 **正在同步最新價格...** (請稍候約 10-20 秒)")
    final_data, last_ts = auto_fetch_all(urls)

    if final_data:
        st.success(f"✅ 數據已自動同步 (最後更新: {last_ts})")
        
        # 顯示大圖網格
        grid = st.columns(3)
        for i, item in enumerate(final_data):
            with grid[i % 3]:
                # 顯示大圖
                st.image(item["圖片"], use_container_width=True)
                # 顯示卡名 (唔再要 ID: ... 字眼)
                st.markdown(f"**{item['名稱']}**")
                
                # 四數據數據框
                st.markdown(f"""
                <div style="font-size: 14px; border: 1px solid #eee; padding: 12px; border-radius: 8px; background-color: #ffffff; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <div style="display: flex
