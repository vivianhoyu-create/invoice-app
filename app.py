import streamlit as st
import pandas as pd
import easyocr
import re
from PIL import Image
import numpy as np
from datetime import datetime
import io

# 設定頁面資訊
st.set_page_config(page_title="統一發票匯集器", layout="wide")

# 初始化 OCR 引擎 (中文+英文)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ch_tra', 'en'])

reader = load_ocr()

# 初始化 Session State 用於儲存表格資料
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=[
        "賣方統編", "發票日期", "發票號碼", "項目", "憑證金額", "原幣稅額"
    ])

def extract_info(image):
    # 將圖片轉換為 numpy array 供 easyocr 使用
    img_array = np.array(image)
    results = reader.readtext(img_array, detail=0)
    full_text = " ".join(results)
    
    # 1. 紀錄賣方統一編號 (8位數字)
    seller_id = re.search(r'\b\d{8}\b', full_text)
    seller_id = seller_id.group(0) if seller_id else ""
    
    # 2. 發票日期 (yyyy/mm/dd) - 支援民國轉西元或直接抓取
    date_match = re.search(r'(\d{3,4})[/.-](\d{2})[/.-](\d{2})', full_text)
    date_str = ""
    if date_match:
        y, m, d = date_match.groups()
        if len(y) == 3: # 民國轉西元
            y = str(int(y) + 1911)
        date_str = f"{y}/{m}/{d}"
    
    # 3. 發票號碼 (兩位英文-8位數字 -> 移除 "-")
    inv_match = re.search(r'([A-Z]{2})[- ]?(\d{8})', full_text)
    inv_number = (inv_match.group(1) + inv_match.group(2)) if inv_match else ""
    
    # 4. 項目 (95汽油 XX.XXX L)
    # 尋找 95 關鍵字後面的浮點數
    fuel_match = re.search(r'95.*?\s?(\d+\.\d{3})', full_text)
    liters = fuel_match.group(1) if fuel_match else "00.000"
    item_desc = f"95汽油 {liters} L"
    
    # 5. 銷售額與稅額 (簡單邏輯：通常較大的數字是銷售額)
    # 這裡建議以正規表達式抓取「銷售額」關鍵字後的數字，若無則留空手動編輯
    sales_match = re.search(r'(銷售額|Amount)[: ]*(\d+)', full_text)
    tax_match = re.search(r'(稅額|Tax)[: ]*(\d+)', full_text)
    
    sales_amt = sales_match.group(2) if sales_match else ""
    tax_amt = tax_match.group(2) if tax_match else ""
    
    return {
        "賣方統編": seller_id,
        "發票日期": date_str,
        "發票號碼": inv_number,
        "項目": item_desc,
        "憑證金額": sales_amt,
        "原幣稅額": tax_amt
    }

# --- UI 介面 ---
st.title("🧾 統一發票匯集器")
st.info("請上傳或拍攝發票，系統將自動提取資訊並彙整至下方表格。")

# 拍照/上傳組件
img_file = st.camera_input("拍照掃描發票") or st.file_uploader("或上傳發票照片", type=['jpg', 'jpeg', 'png'])

if img_file:
    image = Image.open(img_file)
    with st.spinner('正在辨識中...'):
        data = extract_info(image)
        
        # 顯示預覽與確認按鈕
        st.subheader("辨識結果預覽")
        col1, col2 = st.columns(2)
        with col1:
            st.image(image, caption="原始照片", use_container_width=True)
        with col2:
            st.write(data)
            if st.button("確認加入表格"):
                new_row = pd.DataFrame([data])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                st.success("已記錄！")

st.divider()

# --- 表格編輯區 ---
st.subheader("📊 發票彙整清單 (可直接點擊修改)")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 更新儲存狀態
st.session_state.df = edited_df

# --- 匯出區 ---
if not st.session_state.df.empty:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state.df.to_excel(writer, index=False, sheet_name='發票紀錄')
    
    st.download_button(
        label="📥 匯出 Excel 檔案",
        data=output.getvalue(),
        file_name=f"發票彙整_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if st.button("清空所有紀錄"):
    st.session_state.df = pd.DataFrame(columns=["賣方統編", "發票日期", "發票號碼", "項目", "憑證金額", "原幣稅額"])
    st.rerun()
