import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import pandas as pd
from deep_translator import GoogleTranslator

# 網頁基本設定
st.set_page_config(page_title="TCG Admin Quant", page_icon="🔐", layout="wide")

# --- 1. 確保環境 ---
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

# --- 2. 爬蟲核心 ---
def fetch_card_data(url, target_lang):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            raw_title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "未知卡片"
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            
            try:
                translated_name = GoogleTranslator(source='auto', target=target_lang).translate(jp_name)
            except:
                translated_name = jp_name

            text_blocks = list(soup.stripped_strings)
            def find_v(keyword, unit):
                for i, text in enumerate(text_blocks):
                    if keyword in text:
                        for j in range(1, 10):
                            if i + j < len(text_blocks) and unit in text_blocks[i+j]:
                                return text_blocks[i+j]
                return "N/A"

            card_id = url.rstrip('/').split('/')[-1].upper()
            return {
                "卡片編號": card_id,
                "翻譯名稱": translated_name,
                "日文名稱": jp_name,
                "美品価格": find_v("美品価格", "円"),
                "PSA10価格": find_v("PSA10価格", "円"),
                "差額": find_v("差額", "円"),
                "溢價比率": find_v("比率", "%")
            }
        except:
            return None
        finally:
            browser.close()

# --- 3. UI 介面 ---
st.title("🔐 TCG Quant 監控面板 (管理員版)")

# 側欄：身分驗證
st.sidebar.header("🛡️ 身分驗證")
admin_password = st.sidebar.text_input("輸入管理員密碼以解鎖編輯功能:", type="password")

# 預設名單 (你可以喺 GitHub 呢度改死佢，作為最底層嘅名單)
default_urls_list = [
    "https://grading.pokeca-chart.com/sm8b-219-150/",
    "https://grading.pokeca-chart.com/m2a-250-193/"
]

# 判斷係咪管理員
if admin_password == "8888": # <--- 喺呢度改你想要嘅密碼
    st.sidebar.success("✅ 管理員已登入")
    urls_text = st.sidebar.text_area("🔧 編輯監控清單 (每行一個網址):", value="\n".join(default_urls_list), height=300)
else:
    if admin_password != "":
        st.sidebar.error("❌ 密碼錯誤")
    st.sidebar.info("💡 目前為唯讀模式。如需修改清單，請輸入管理員密碼。")
    urls_text = "\n".join(default_urls_list)

# 語言選擇
lang_choice = st.sidebar.selectbox("翻譯語言:", ("中文 (繁體)", "English"))
target_lang_code = 'zh-TW' if lang_choice == "中文 (繁體)" else 'en'

target_urls = [line.strip() for line in urls_text.split("\n") if line.strip()]

# 4. 執行與展示
if st.button(f"🚀 更新所有監控目標 ({len(target_urls)} 張)"):
    results = []
    progress_bar = st.progress(0)
    
    for idx, url in enumerate(target_urls):
        st.write(f"正在分析: {url.split('/')[-2]}...")
        data = fetch_card_data(url, target_lang_code)
        if data:
            results.append(data)
        progress_bar.progress((idx + 1) / len(target_urls))
    
    if results:
        df = pd.DataFrame(results)
        st.divider()
        st.subheader(f"📋 市場實時報告")
        df = df[["卡片編號", "翻譯名稱", "美品価格", "PSA10価格", "差額", "溢價比率"]]
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載數據匯總", csv, "tcg_report.csv", "text/csv")

st.divider()
st.caption("阿強 Admin Quant System | 只有擁有密碼嘅人先可以修改名單")
