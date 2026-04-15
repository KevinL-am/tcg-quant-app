import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
import os
from datetime import datetime

st.set_page_config(page_title="TCG Master Quant", page_icon="🔮", layout="wide")

# --- 1. 定製大師球 CSS (Master Ball Style) ---
st.markdown("""
    <style>
    /* 大師球更新掣樣式 */
    div.stButton > button:first-child {
        background-color: #6a1b9a; /* 大師球紫色 */
        color: white;
        border-radius: 50%;
        width: 120px;
        height: 120px;
        border: 8px solid #333;
        font-size: 50px;
        font-weight: bold;
        box-shadow: 0 8px 15px rgba(0,0,0,0.4);
        display: block;
        margin-left: auto;
        margin-right: auto;
        transition: all 0.3s ease;
        line-height: 1;
    }
    div.stButton > button:first-child:hover {
        background-color: #8e24aa;
        transform: scale(1.1) rotate(10deg);
        border-color: #ff0000;
    }
    div.stButton > button:first-child:active {
        transform: scale(0.9);
    }
    .master-label {
        text-align: center;
        font-weight: bold;
        color: #6a1b9a;
        margin-top: 10px;
        font-size: 18px;
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

# --- 3. 爬蟲核心 (Playwright 定點追蹤版) ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

def fetch_card_data_master(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 模擬手機/高清電腦，確保表格彈出嚟
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000) # 等 5 秒確保 JS 跑完
            
            # 1. 攞卡名
            jp_name = page.locator("h1").inner_text().split('の')[0]
            
            # 2. 攞圖片
            img_element = page.locator("div.product-image img, main img").first
            img_url = img_element.get_attribute("src")
            if img_url and not img_url.startswith("http"):
                img_url = f"https://grading.pokeca-chart.com{img_url}"

            # 3. 💡 定點追蹤：直接搵 th 隔離嗰個 td (新域名 grading 專用)
            def get_val(label):
                try:
                    # 搵包含該文字嘅 th 標籤，然後攞佢後面嘅 td 內容
                    return page.locator(f"th:has-text('{label}') + td").inner_text(timeout=5000)
                except:
                    return "N/A"

            bihin = get_val("美品価格")
            psa10 = get_val("PSA10価格")
            diff = get_val("差額")
            ratio = get_val("比率")
                
            return {
                "名稱": jp_name, "圖片": img_url,
                "美品": bihin, "PSA10": psa10, "差額": diff, "比率": ratio
            }
        except Exception as e:
            return None
        finally:
            browser.close()

# --- 4. UI 介面 ---
st.title("🛡️ TCG Master Quant 專業版")

# 側欄管理
REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("🔑 管理員密碼", type="password")

@st.cache_data(ttl=600)
def get_urls():
    return [v for v in main_sheet.col_values(1) if v.startswith("http")]

urls = get_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖大師權限")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(urls), height=200)
    if st.sidebar.button("💾 儲存名單"):
        rows = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if rows: main_sheet.update('A1', rows)
        st.cache_data.clear()
        st.rerun()
else:
    st.sidebar.info("唯讀模式 (請輸入密碼解鎖)")

# --- 🎯 大師球手動觸發區 ---
st.divider()
st.write("")
# 居中顯示大師球按鈕
c1, c2, c3 = st.columns([1, 1, 1])
with c2:
    # 呢粒就係大佬要嘅「大師球」！
    master_click = st.button("M") 
    st.markdown('<p class="master-label">按此啟動大師球更新</p>', unsafe_allow_html=True)

if master_click:
    if not urls:
        st.warning("名單係空嘅，捉唔到嘢呀大佬！")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 顯示進度
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, url in enumerate(urls):
            status.write(f"🔍 大師球正在捕捉第 {i+1} 張卡數據...")
            data = fetch_card_data_master(url)
            if data:
                results.append(data)
            progress_bar.progress((i + 1) / len(urls))
        
        status.success(f"🎊 捕捉完成！最後更新：{now}")

        if results:
            # 同步到 Google Sheet
            if history_sheet:
                history_rows = [[now, i["名稱"], f'=IMAGE("{i["圖片"]}")', i["PSA10"], i["美品"], i["差額"], i["比率"]] for i in results]
                history_sheet.append_rows(history_rows)
            
            # 顯示結果
            st.divider()
            grid = st.columns(3)
            for idx, item in enumerate(results):
                with grid[idx % 3]:
                    st.image(item["圖片"], use_container_width=True)
                    st.markdown(f"**{item['名稱']}**")
                    st.markdown(f"""
                    <div style="font-size: 14px; border: 2px solid #6a1b9a; padding: 12px; border-radius: 10px; background-color: #f3e5f5;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="color: #e67e22; font-weight: bold;">● 美品：</span><b>{item['美品']}</b>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="color: #3498db; font-weight: bold;">● PSA10：</span><b>{item['PSA10']}</b>
                        </div>
                        <div style="border-top: 1px dashed #6a1b9a; margin-top: 8px; padding-top: 8px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
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
    st.info("💡 系統已就緒。請撳上面粒「大師球」開始更新數據。")

st.divider()
st.caption("阿強 Cloud Pro | 大師球手動模式")
