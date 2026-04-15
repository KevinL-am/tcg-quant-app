import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime

st.set_page_config(page_title="TCG Master Ball Quant", page_icon="🔮", layout="wide")

# --- 1. 終極大師球 CSS (紫色上、白色下) ---
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background: linear-gradient(#6a1b9a 50%, #ffffff 50%);
        color: white; /* 呢個係 M 字色 */
        border-radius: 50%;
        width: 180px;
        height: 180px;
        border: 12px solid #333;
        font-size: 80px !important;
        font-weight: 900;
        box-shadow: 0 10px 20px rgba(0,0,0,0.5);
        display: block;
        margin: 20px auto;
        transition: all 0.2s ease;
        line-height: 0.8; /* 調整 M 字位置向上移入紫色區 */
        padding-bottom: 40px; 
    }
    div.stButton > button:first-child:hover {
        transform: scale(1.05) rotate(-5deg);
        border-color: #ff0000;
    }
    .master-label {
        text-align: center;
        font-weight: 900;
        color: #6a1b9a;
        font-size: 24px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 連接 Google Sheets ---
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

# --- 3. 爬蟲核心 (初代暴力搜尋 + 現代精準定位) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_master_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 唔加載圖片同 CSS 去換取速度
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        try:
            # 1. 快速加載
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # 2. 只等表格出現，唔等成個 Page Load 完
            try:
                page.wait_for_selector("table", timeout=10000)
            except:
                pass 
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # --- 捉名稱與圖片 ---
            jp_name = soup.find('h1').get_text(strip=True).split('の')[0] if soup.find('h1') else "未知"
            img_tag = soup.find('div', class_='product-image') or soup.find('main').find('img') or soup.find('img')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://grading.pokeca-chart.com{src}"

            # --- 💡 雙重捉數邏輯 ---
            res = {"美品": "N/A", "PSA10": "N/A", "差額": "N/A", "比率": "N/A"}
            
            # A. 現代精準版：搵 Table 內對應嘅 td
            rows = soup.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    txt = th.get_text(strip=True)
                    val = td.get_text(strip=True)
                    if "美品価格" in txt: res["美品"] = val
                    elif "PSA10価格" in txt: res["PSA10"] = val
                    elif "差額" in txt: res["差額"] = val
                    elif "比率" in txt: res["比率"] = val

            # B. 初代暴力版：如果仲係 N/A，掃全網 Text
            if res["美品"] == "N/A" or res["PSA10"] == "N/A":
                all_text = list(soup.stripped_strings)
                for i, s in enumerate(all_text):
                    if "美品価格" in s and res["美品"] == "N/A" and i+1 < len(all_text):
                        if "円" in all_text[i+1]: res["美品"] = all_text[i+1]
                    if "PSA10価格" in s and res["PSA10"] == "N/A" and i+1 < len(all_text):
                        if "円" in all_text[i+1]: res["PSA10"] = all_text[i+1]

            return {
                "名稱": jp_name, "圖片": img_url,
                "美品": res["美品"], "PSA10": res["PSA10"], 
                "差額": res["差額"], "比率": res["比率"]
            }
        except:
            return None
        finally:
            browser.close()

# --- 4. UI 介面 ---
st.title("🛡️ TCG Master Ball Quant")

# 側欄
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("🔑 大師授權碼", type="password")

@st.cache_data(ttl=600)
def get_urls():
    return [v for v in main_sheet.col_values(1) if v.startswith("http")]

urls = get_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 授權成功")
    new_urls = st.sidebar.text_area("🔧 名單管理:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存名單"):
        rows = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear()
        st.rerun()
else:
    st.sidebar.info("請輸入密碼解鎖大師球")

# --- 🎯 居中大師球 ---
st.write("")
col1, col2, col3 = st.columns([1, 1.5, 1])
with col2:
    master_click = st.button("M") # 呢個 M 字會透過 CSS 擺正位置
    st.markdown('<p class="master-label">MASTER BALL UPDATE</p>', unsafe_allow_html=True)

if master_click:
    if not urls:
        st.warning("名單係空嘅。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        status = st.status("🔮 大師球捕捉中...", expanded=True)
        for i, url in enumerate(urls):
            status.write(f"正在掃瞄 ({i+1}/{len(urls)}): {url.split('/')[-1]}")
            data = fetch_master_data(url)
            if data:
                results.append(data)
        status.update(label="✅ 捕捉完成！", state="complete", expanded=False)

        if results:
            # 寫入歷史
            if history_sheet:
                h_rows = [[now, i["名稱"], f'=IMAGE("{i["圖片"]}")', i["PSA10"], i["美品"], i["差額"], i["比率"]] for i in results]
                history_sheet.append_rows(h_rows)
            
            # 網格顯示
            st.divider()
            grid = st.columns(3)
            for idx, item in enumerate(results):
                with grid[idx % 3]:
                    st.image(item["圖片"], use_container_width=True)
                    st.markdown(f"**{item['名稱']}**")
                    st.markdown(f"""
                    <div style="font-size: 15px; border: 2px solid #6a1b9a; padding: 15px; border-radius: 12px; background-color: #f9f4ff; box-shadow: 2px 2px 10px rgba(106, 27, 154, 0.1);">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="color: #e67e22; font-weight: bold;">● 美品：</span><b>{item['美品']}</b>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="color: #3498db; font-weight: bold;">● PSA10：</span><b>{item['PSA10']}</b>
                        </div>
                        <div style="border-top: 1px dashed #6a1b9a; margin-top: 10px; padding-top: 10px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="color: #666;">● 差額：</span><b>{item['差額']}</b>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="color: #666;">● 比率：</span><b>{item['比率']}</b>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("")
            st.balloons()
else:
    st.info("💡 點擊上方大師球開始手動更新。")

st.divider()
st.caption("阿強 TCG Cloud Pro | 大師球精準版")
