import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

# --- 페이지 설정 (품앗이 정체성) ---
st.set_page_config(page_title="슬기로운 발주생활", page_icon="🛒", layout="wide")
st.header("품앗이발주비서")

st.title("🛒 품앗이생협 로컬푸드 2.0 발주 시스템")
st.markdown("**'데이터'**를 통해 **'사람(품앗이님)'**을 남기는 정직한 발주를 시작합니다.")
st.markdown("---")

# --- 사이드바: 설정 영역 ---
with st.sidebar:
    st.header("⚙️ 설정")
    target_date = st.date_input("📅 조회 시작 날짜", datetime(2026, 2, 1))
    st.info("선택한 날짜부터 오늘까지의 판매량을 분석합니다.")

# --- 메인: 파일 업로드 영역 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. 기준표 (체크리스트)")
    uploaded_checklist = st.file_uploader("★매입처_체크리스트.xlsx 파일을 올려주세요", type=['xlsx'])

with col2:
    st.subheader("2. 판매 데이터 (POS)")
    uploaded_sale = st.file_uploader("직매장 농가별 판매 엑셀 파일을 올려주세요", type=['xlsx'])

# --- 분석 로직 ---
if uploaded_checklist and uploaded_sale:
    if st.button("🚀 발주 분석 시작하기", type="primary"):
        try:
            with st.spinner('데이터를 분석하고 우선순위를 정하는 중입니다...'):
                # 1. 기준표 읽기
                vendor_df = pd.read_excel(uploaded_checklist, sheet_name='1.업체선정', engine='openpyxl')
                selected_vendors = vendor_df[vendor_df.iloc[:, 1].notna()]['업체명(농가명)'].astype(str).tolist()

                # 2. 판매 데이터 읽기 (9행부터)
                df = pd.read_excel(uploaded_sale, header=8, engine='openpyxl')
                df.columns = [str(c).replace(' ', '').replace('\n', '') for c in df.columns]

                # 3. 데이터 필터링 (날짜 & 업체)
                if '판매일시' in df.columns:
                    df['판매일시'] = pd.to_datetime(df['판매일시'])
                    df = df[df['판매일시'] >= pd.to_datetime(target_date)]
                
                mask_vendor = df['농가명'].isin(selected_vendors)
                final_df = df[mask_vendor]

                if final_df.empty:
                    st.error("⚠️ 해당 기간/업체의 판매 내역이 없습니다.")
                else:
                    # 4. 집계 및 정렬 (인기순)
                    agg_dict = {'판매일시': 'count', '수량': 'sum', '결제금액': 'sum'}
                    grouped = final_df.groupby(['농가명', '품목명', '단위']).agg(agg_dict).reset_index()
                    grouped.rename(columns={'판매일시': '판매건수(인기)'}, inplace=True)
                    grouped = grouped.sort_values(by=['판매건수(인기)', '수량'], ascending=[False, False])

                    # 5. 결과 보여주기 (미리보기)
                    st.success(f"✅ 분석 완료! 총 {len(grouped)}개 품목이 발주 대상입니다.")
                    
                    # Top 5 카드 보여주기
                    st.subheader("🏆 품앗이님들이 가장 많이 찾은 Top 5")
                    top5 = grouped.head(5)
                    st.table(top5[['농가명', '품목명', '판매건수(인기)', '수량', '결제금액']])

                    # 6. 엑셀 다운로드 생성 (메모리 내 작성)
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        # 전체 시트
                        grouped.to_excel(writer, sheet_name='전체통합_우선순위', index=False)
                        
                        # 업체별 시트
                        for vendor in grouped['농가명'].unique():
                            v_data = grouped[grouped['농가명'] == vendor]
                            v_data = v_data.sort_values(by=['판매건수(인기)'], ascending=False)
                            safe_name = re.sub(r'[\\/*?:\[\]]', '', str(vendor))[:30]
                            v_data.to_excel(writer, sheet_name=safe_name, index=False)
                    
                    output.seek(0)
                    
                    # 다운로드 버튼
                    st.download_button(
                        label="📥 최종 발주서 엑셀 다운로드",
                        data=output,
                        file_name=f"발주서_{target_date.strftime('%Y%m%d')}이후.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

else:

    st.info("👆 위 두 개의 파일을 업로드하면 분석 버튼이 나타납니다.")
