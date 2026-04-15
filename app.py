import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import pandas as pd

st.set_page_config(page_title="TCG Portfolio Quant", page_icon="📊", layout="wide")

st.title("📊 TCG Quant 持倉監控面板")
st.markdown("一次過監控多張目標卡片，實時分析溢價機會。")

# 1. 確保 Playwright 環境
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

# 2. 爬蟲核心 (單次抓取)
def fetch_card_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
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
                "美品価格": find_v("美品価格", "円"),
                "PSA10価格": find_v("PSA10価格", "円"),
                "差額": find_v("差額", "円"),
                "溢價比率": find_v("比率", "%")
            }
        except:
            return None
        finally:
            browser.close()

# 3. UI 介面 - 管理監控清單
st.sidebar.header("⚙️ 監控名單管理")
# 預設一啲卡片畀你測試
default_urls = [
    "https://grading.pokeca-chart.com/sm8b-219-150/",
    "https://grading.pokeca-chart.com/m2a-250-193/"
]

# 讓用戶輸入多個網址，一行一個
urls_text = st.sidebar.text_area("貼入網址清單 (每行一個):", value="\n".join(default_urls), height=200)
target_urls = [line.strip() for line in urls_text.split("\n") if line.strip()]

# 4. 執行按鈕
if st.button(f"🚀 開始更新所有卡片 ({len(target_urls)} 張)"):
    results = []
    progress_bar = st.progress(0)
    
    for idx, url in enumerate(target_urls):
        st.write(f"正在抓取: {url} ...")
        data = fetch_card_data(url)
        if data:
            results.append(data)
        progress_bar.progress((idx + 1) / len(target_urls))
    
    # 5. 展示匯總表格
    if results:
        df = pd.DataFrame(results)
        st.divider()
        st.subheader("📋 實時市場數據匯總")
        st.dataframe(df, use_container_width=True)
        
        # 簡單分析：邊張最抵 (假設溢價比率越低越有潛力)
        st.info("💡 提示：你可以點擊表格標題進行排序，快速搵出溢價最低嘅卡片。")
    else:
        st.error("所有卡片抓取失敗，請檢查網址或稍後再試。")

st.divider()
st.caption("阿強 TCG Dashboard | 支援同時監控無限張卡片")
