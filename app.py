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

# --- 2. 爬蟲核心 (四數據精準版) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 捉卡片編號
            card_id = url.rstrip('/').split('/')[-1].upper()
            
            # 捉名稱 (唔再翻譯，直接攞日文)
            h1_tag = soup.find('h1')
            jp_name = h1_tag.get_text(strip=True).split('の')[0] if h1_tag else "未知"
            
            # 捉圖片
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"
            
            # 💡 重點：四數據表格抓取
            res = {"bihin": "N/A", "psa10": "N/A", "diff": "N/A", "ratio": "N/A"}
            rows = soup.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    lbl = th.get_text(strip=True)
                    val = td.get_text(strip=True)
                    if "美品価格" in lbl: res["bihin"] = val
                    elif "PSA10価格" in lbl: res["psa10"] = val
                    elif "差額" in lbl: res["diff"] = val
                    elif "比率" in lbl: res["ratio"] = val
            
            return {
                "卡片編號": card_id, "名稱": jp_name, "圖片": img_url,
                "美品": res["bihin"], "PSA10": res["psa10"], "差額": res["diff"], "比率": res["ratio"]
            }
        except: return None
        finally: browser.close()

# --- 3. UI 介面與自動執行 ---
st.title("🚀 TCG Quant 終極全自動監控")

# 密碼與名單管理
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

@st.cache_data(ttl=300)
def get_cloud_urls():
    return [v for v in main_sheet.col_values(1) if v.startswith("http")]

urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存並即時更新"):
        rows = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear() 
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")

# --- 🚀 自動更新任務 (一開就 Load) ---
if not urls:
    st.info("👈 請喺側欄輸入網址名單。")
else:
    @st.cache_data(ttl=3600) # 每小時自動爬一次
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

    st.write("🔄 **正在自動掃瞄數據...**")
    final_data, last_time = auto_update(urls)

    if final_data:
        st.success(f"✅ 數據已更新至最新 ({last_time})")
        grid = st.columns(3)
        for i, item in enumerate(final_data):
            with grid[i % 3]:
                st.image(item["圖片"], use_container_width=True)
                st.markdown(f"**{item['名稱']}**")
                st.caption(f"ID: {item['卡片編號']}")
                
                # 四數據專業排版
                st.markdown(f"""
                <div style="font-size: 14px; border: 1px solid #eee; padding: 10px; border-radius: 5px; background-color: #fcfcfc;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #e67e22;">● 美品：</span><b>{item['美品']}</b>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #3498db;">● PSA10：</span><b>{item['PSA10']}</b>
                    </div>
                    <div style="display: flex; justify-content: space-between; border-top: 1px dashed #ccc; margin-top: 5px; padding-top: 5px;">
                        <span style="color: #666;">● 差額：</span><b>{item['差額']}</b>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #666;">● 比率：</span><b>{item['比率']}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

st.divider()
st.caption("阿強 Cloud Pro | 四數據自動追蹤系統")
