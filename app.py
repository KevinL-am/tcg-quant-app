import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import pandas as pd
from deep_translator import GoogleTranslator # 引入 AI 翻譯組件

st.set_page_config(page_title="TCG Global Quant", page_icon="🌐", layout="wide")

st.title("🌐 TCG Quant 持倉監控 (AI 多國語言版)")
st.markdown("自動抓取日文數據並即時翻譯為中文/英文。")

# 1. 確保環境
@st.cache_resource
def install_browser():
    os.system("playwright install chromium")
install_browser()

# 2. 爬蟲 + 翻譯核心
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
            
            # 抓取日文名
            raw_title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "未知卡片"
            jp_name = raw_title.replace("のPSA10/美品価格推移", "").replace("のPSA10/美品買取価格推移", "")
            
            # --- AI 翻譯步驟 ---
            try:
                # 將日文 (ja) 翻譯去 目標語言 (zh-TW 或 en)
                translated_name = GoogleTranslator(source='auto', target=target_lang).translate(jp_name)
            except:
                translated_name = jp_name # 萬一翻譯失敗就用返日文

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
                "日文名稱": jp_name,
                "AI 翻譯名稱": translated_name,
                "美品価格": find_v("美品価格", "円"),
                "PSA10価格": find_v("PSA10価格", "円"),
                "差額": find_v("差額", "円"),
                "溢價比率": find_v("比率", "%")
            }
        except:
            return None
        finally:
            browser.close()

# 3. UI 側欄
st.sidebar.header("⚙️ 系統設定")

# 讓用戶選擇翻譯語言
lang_choice = st.sidebar.selectbox(
    "選擇翻譯語言:",
    ("中文 (繁體)", "English"),
    index=0
)
target_lang_code = 'zh-TW' if lang_choice == "中文 (繁體)" else 'en'

default_urls = [
    "https://grading.pokeca-chart.com/sm8b-219-150/",
    "https://grading.pokeca-chart.com/m2a-250-193/"
]
urls_text = st.sidebar.text_area("貼入網址清單:", value="\n".join(default_urls), height=200)
target_urls = [line.strip() for line in urls_text.split("\n") if line.strip()]

# 4. 執行
if st.button(f"🚀 開始更新並翻譯 ({len(target_urls)} 張卡)"):
    results = []
    progress_bar = st.progress(0)
    
    for idx, url in enumerate(target_urls):
        st.write(f"正在分析並翻譯: {url.split('/')[-2]}...")
        data = fetch_card_data(url, target_lang_code)
        if data:
            results.append(data)
        progress_bar.progress((idx + 1) / len(target_urls))
    
    if results:
        df = pd.DataFrame(results)
        st.divider()
        st.subheader(f"📋 實時市場報告 ({lang_choice})")
        # 欄位排序
        df = df[["卡片編號", "AI 翻譯名稱", "日文名稱", "美品価格", "PSA10価格", "差額", "溢價比率"]]
        st.dataframe(df, use_container_width=True)
    else:
        st.error("抓取失敗，請檢查網址。")

st.divider()
st.caption("阿強 AI TCG Quant | 支援 Google AI 即時翻譯")
