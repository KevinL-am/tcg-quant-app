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

# --- 2. 爬蟲核心 (雷達校準版) ---
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
            
            card_id = url.rstrip('/').split('/')[-1].upper()
            h1_tag = soup.find('h1')
            raw_title = h1_tag.get_text(strip=True) if h1_tag else "未知"
            jp_name = raw_title.replace("のPSA10/美品價格推移", "").replace("推移", "")
            
            # 捉圖片
            img_tag = soup.find('main').find('img') or soup.find('img', class_='product-image')
            img_url = "N/A"
            if img_tag:
                src = img_tag.get('src') or img_tag.get('data-src')
                img_url = src if src.startswith('http') else f"https://pokeca-chart.com{src}"
            
            name_ch = GoogleTranslator(source='auto', target='zh-TW').translate(jp_name)
            
            # 💡 重點修正：更強大的價錢定位雷達
            text_blocks = list(soup.stripped_strings)
            
            def find_price_refined(keywords):
                for i, text in enumerate(text_blocks):
                    # 只要區塊包含關鍵字 (例如 "美品")
                    if any(k in text for k in keywords):
                        # 檢查呢個區塊本身係咪已經帶有 "円" (有時標籤同價錢喺埋一齊)
                        if "円" in text:
                            # 提取數字部分 (例如: 美品價格：12,000円 -> 12,000円)
                            return text.split('：')[-1].split(':')[-1]
                        
                        # 否則向後搵 3 格
                        for j in range(1, 4):
                            if i + j < len(text_blocks):
                                next_text = text_blocks[i+j]
                                if "円" in next_text:
                                    return next_text
                return "N/A"

            # 分開精確關鍵字去搵
            bi_hin = find_price_refined(["美品価格", "美品買取"])
            psa10 = find_price_refined(["PSA10価格", "PSA10買取"])
                
            return {
                "卡片編號": card_id,
                "名稱": name_ch,
                "圖片": img_url,
                "美品価格": bi_hin, 
                "PSA10価格": psa10
            }
        except: return None
        finally: browser.close()

# --- 3. UI 介面 ---
st.title("📊 TCG Quant 精細監控版")

REAL_PW = st.secrets.get("admin_password", "8888")
pw = st.sidebar.text_input("管理員密碼", type="password")

@st.cache_data(ttl=60)
def get_cloud_urls():
    try: return [v for v in main_sheet.col_values(1) if v.startswith("http")]
    except: return []

cloud_urls = get_cloud_urls()

if pw == REAL_PW:
    st.sidebar.success("✅ 已解鎖")
    new_urls = st.sidebar.text_area("🔧 編輯名單:", value="\n".join(cloud_urls), height=200)
    if st.sidebar.button("💾 儲存並同步"):
        urls_to_save = [[u.strip()] for u in new_urls.split("\n") if u.strip()]
        main_sheet.clear()
        if urls_to_save: main_sheet.update('A1', urls_to_save)
        st.sidebar.balloons()
        st.rerun()
else:
    st.sidebar.info("💡 唯讀模式")
    new_urls = "\n".join(cloud_urls)

target_list = [l.strip() for l in new_urls.split("\n") if l.strip()]

if st.button(f"🚀 更新數據並寫入歷史 ({len(target_list)} 張)"):
    if not target_list:
        st.warning("名單係空嘅。")
    else:
        results = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        progress = st.progress(0)
        status_box = st.empty()
        
        for i, url in enumerate(target_list):
            card_id = url.rstrip('/').split('/')[-1]
            status_box.write(f"正在更新: {card_id}")
            data = fetch_card_data(url)
            if data: results.append(data)
            progress.progress((i + 1) / len(target_list))
        
        status_box.empty()
        
        if results:
            st.divider()
            grid_cols = st.columns(3)
            
            for i, item in enumerate(results):
                with grid_cols[i % 3]:
                    st.image(item["圖片"], use_container_width=True)
                    st.caption(f"ID: {item['卡片編號']}")
                    st.markdown(f"**{item['名稱']}**")
                    
                    # 顯示價錢，加強排版
                    st.markdown(f"""
                    <div style="font-size: 14px; border-top: 1px solid #eee; padding-top: 8px; line-height: 1.6;">
                        <span style="color: #e67e22; font-weight: bold;">美品：</span> <span>{item['美品価格']}</span><br>
                        <span style="color: #3498db; font-weight: bold;">PSA10：</span> <span>{item['PSA10価格']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.write("") 
            
            if history_sheet:
                history_rows = [[now, item["卡片編號"], item["名稱"], f'=IMAGE("{item["圖片"]}")', item["PSA10価格"], item["美品価格"]] for item in results]
                history_sheet.append_rows(history_rows)
                st.toast(f"✅ 歷史數據已同步！", icon="📉")

st.divider()
st.caption("阿強 Cloud Pro | 價錢修正版")
