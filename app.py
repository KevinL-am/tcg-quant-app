import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os

# 網頁設定
st.set_page_config(page_title="TCG Quant Tracker", page_icon="📈")

st.title("📈 阿強 TCG Quant 實時監控系統")
st.markdown("針對 Pokeca-chart 嘅動態數據抓取引擎已啟動。")
st.divider()

# 雲端自動安裝 Playwright 瀏覽器
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

# 爬蟲核心
def fetch_data(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        try:
            # 暴力破門模式
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000) # 強行等待 5 秒讓 JS 載入價錢
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            text_blocks = list(soup.stripped_strings)
            
            def find_value(keyword, unit):
                for i, text in enumerate(text_blocks):
                    if keyword in text:
                        for j in range(1, 16):
                            if i + j < len(text_blocks) and unit in text_blocks[i+j]:
                                return text_blocks[i+j]
                return "未搵到"

            return {
                "raw": find_value("美品価格", "円"),
                "psa": find_value("PSA10価格", "円"),
                "spread": find_value("差額", "円"),
                "ratio": find_value("比率", "%")
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            browser.close()

# 介面
url_input = st.text_input("🔗 請輸入 Pokeca-chart 網址:", placeholder="https://grading.pokeca-chart.com/...")
if st.button("🚀 執行深度抓取") and url_input:
    card_code = url_input.rstrip('/').split('/')[-1].upper()
    with st.spinner(f"🤖 阿強正在潛入伺服器抓取 {card_code}..."):
        result = fetch_data(url_input)
        
        if "error" in result:
            st.error(f"抓取超時: {result['error']}")
        else:
            st.success(f"✅ 成功獲取 {card_code} 實時報價！")
            c1, c2 = st.columns(2)
            c1.metric("裸卡 (美品)", result["raw"])
            c2.metric("PSA 10 價格", result["psa"])
            
            c3, c4 = st.columns(2)
            c3.metric("差額", result["spread"])
            c4.metric("溢價比率", result["ratio"])
            
st.divider()
st.caption("阿強 TCG Market Quant 系統 | Powered by Streamlit & Playwright")