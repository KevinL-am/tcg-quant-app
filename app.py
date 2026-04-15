import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import re # 引入正則表達式做精確匹配
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

# --- 2. 爬蟲核心 (暴力關鍵字版) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # 模擬真實瀏覽器
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000) # 畀多啲時間等佢 Load 晒啲數
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 捉卡片編號與名稱
            card_id = url.rstrip('/').split('/')[-1].upper()
            h1_tag = soup.find('h1')
            jp_name = h1_tag.get_text(strip=True).split('の')[0] if h1_tag else "未知"
            
            # 捉圖片
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img') or soup.find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            # 💡 終極方案：唔管結構，直接掃瞄所有文字區塊
            res = {"bihin": "N/A", "psa10": "N/A", "diff": "N/A", "ratio": "N/A"}
            all_strings = list(soup.stripped_strings)
            
            for i, s in enumerate(all_strings):
                if "美品価格" in s and res["bihin"] == "N/A":
                    if i + 1 < len(all_strings): res["bihin"] = all_strings[i+1]
                elif "PSA10価格" in s and res["psa10"] == "N/A":
                    if i + 1 < len(all_strings): res["psa10"] = all_strings[i+1]
                elif "差額" in s and res["diff"] == "N/A":
                    if i + 1 < len(all_strings): res["diff"] = all_strings[i+1]
                elif "比率" in s and res["ratio"] == "N/A":
                    if i + 1 < len(all_strings): res["ratio"] = all_strings[i+1]
            
            return {
                "卡片編號": card_id, "名稱": jp_name, "圖片": img_url,
                "美品": res["bihin"], "PSA10": res["psa10"], "差額": res["diff"], "比率": res["ratio"]
            }
        except: return None
        finally: browser.close()

# --- 3. UI 與自動更新 ---
st.title("📊 TCG Quant 全自動大圖版")

# 密碼管理
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

@st.cache_data(ttl=600)
def get_cloud_urls():
    return [v for v in main_sheet.col_values(1) if v.startswith("http")]

urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 身分已確認")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存並同步"):
        rows = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear() 
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")

# --- 🚀 自動 Load 任務 ---
if not urls:
    st.info("👈 請喺側欄輸入網址名單。")
else:
    @st.cache_data(ttl=3600)
    def auto_update(url_list):
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for url in url_list:
            data = fetch_card_data(url)
            if data: results.append(data)
        
        if history_sheet and results:
            history_rows = [[now, i["卡片編號"], i["名稱"], f'=IMAGE("{i["圖片"]}")', i["PSA10"], i["美品"], i["差額"], i["比率"]] for i in results]
            history_sheet.append_rows(history_rows)
        return results, now

    st.write("🔄 **正在檢查最新價格...**")
    final_data, last_ts = auto_update(urls)

    if final_data:
        st.success(f"✅ 更新完成 (更新時間: {last_ts})")
        grid = st.columns(3)
        for i, item in enumerate(final_
