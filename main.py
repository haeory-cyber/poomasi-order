import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from collections import Counter
import koreanize_matplotlib # 한글 폰트 자동 설정

# ---------------------------------------------------------
# [기본 설정] 페이지 및 디자인
# ---------------------------------------------------------
st.set_page_config(page_title="슬기로운 발주생활", page_icon="🛒", layout="wide")

st.title("슬기로운 발주생활 🛒")
st.markdown("### 품앗이생협 통합 업무 지원 시스템 (발주 & 마케팅)")

# ---------------------------------------------------------
# [공통] 파일 업로드 섹션 (사이드바 또는 상단)
# ---------------------------------------------------------
st.info("💡 **매입처 기준표**와 **POS 판매 데이터**를 업로드하면, 발주서와 마케팅 전략이 동시에 생성됩니다!")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. 기준표 (체크리스트)")
    uploaded_file_standard = st.file_uploader("★매입처_체크리스트.xlsx 파일을 올려주세요", type=['xlsx'])

with col2:
    st.subheader("2. 판매 데이터 (POS)")
    uploaded_file_sales = st.file_uploader("직매장 판매내역 엑셀(행복ICT)을 올려주세요", type=['xlsx', 'csv'])

# ---------------------------------------------------------
# [탭 설정] 업무 공간 분리
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 발주 비서 (재고관리)", "💡 마케팅 비서 (전략분석)"])

# 데이터가 둘 다 있을 때만 작동
if uploaded_file_standard and uploaded_file_sales:
    
    # 데이터 로드 (공통 사용)
    df_std = pd.read_excel(uploaded_file_standard)
    
    # 판매 데이터 로드 (xlsx 또는 csv 대응)
    if uploaded_file_sales.name.endswith('.csv'):
        df_sales = pd.read_csv(uploaded_file_sales)
    else:
        df_sales = pd.read_excel(uploaded_file_sales)

    # =========================================================
    # [Tab 1] 발주 비서 로직 (기존 기능)
    # =========================================================
    with tab1:
        st.markdown("### 📋 품앗이님들이 많이 찾은 상품 발주하기")
        
        if st.button("🚀 발주 분석 시작하기", key="order_btn"):
            with st.spinner('데이터를 분석하여 발주서를 만드는 중...'):
                # 1. 판매 데이터 집계 (상품별 판매수량, 금액)
                # POS 데이터 컬럼명에 따라 수정 필요할 수 있음 (기본: '상품명', '수량', '합계')
                # 행복ICT 엑셀 컬럼명 확인 후 필요시 수정: '품목명', '수량', '결제금액' 등
                sales_cols = df_sales.columns
                item_col = '품목명' if '품목명' in sales_cols else '상품명'
                qty_col = '수량'
                amt_col = '결제금액' if '결제금액' in sales_cols else '합계'

                # 데이터 집계
                sales_summary = df_sales.groupby(item_col)[[qty_col, amt_col]].sum().reset_index()
                sales_summary.rename(columns={item_col: '품목명', qty_col: '총판매수량', amt_col: '총판매금액'}, inplace=True)
                
                # 판매건수(인기) 집계 (몇 명이 샀는가)
                sales_count = df_sales[item_col].value_counts().reset_index()
                sales_count.columns = ['품목명', '판매건수(인기)']
                
                # 병합
                final_sales = pd.merge(sales_summary, sales_count, on='품목명', how='left')

                # 2. 기준표와 매칭 (VLOOKUP 개념)
                # 기준표의 '품목명'과 판매데이터의 '품목명'을 기준으로 합침
                merged_df = pd.merge(df_std, final_sales, on='품목명', how='left')

                # 3. 데이터 정리 (NaN 값을 0으로 채움)
                merged_df['총판매수량'] = merged_df['총판매수량'].fillna(0)
                merged_df['판매건수(인기)'] = merged_df['판매건수(인기)'].fillna(0)

                # 4. 정렬 (판매건수 높은 순서대로 = 품앗이님이 자주 찾는 순)
                result_df = merged_df.sort_values(by='판매건수(인기)', ascending=False)

                st.success(f"✅ 분석 완료! 총 {len(result_df)}개 품목이 발주 대상입니다.")
                
                # 상위 5개 미리보기
                st.write("🏆 **품앗이님들이 가장 많이 찾은 Top 5**")
                st.dataframe(result_df[['농가명', '품목명', '판매건수(인기)', '총판매수량']].head(5))

                # 엑셀 다운로드 생성
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # 전체 리스트 시트
                    result_df.to_excel(writer, index=False, sheet_name='전체발주권고')
                    
                    # 농가별 시트 분리 (이게 핵심!)
                    farmers = result_df['농가명'].unique()
                    for farmer in farmers:
                        if pd.isna(farmer): continue
                        farmer_data = result_df[result_df['농가명'] == farmer]
                        # 데이터가 있는 것만 저장 (판매된 것만)
                        # 만약 판매 안 된 것도 보고 싶으면 이 조건을 빼세요.
                        if farmer_data['판매건수(인기)'].sum() > 0: 
                            sheet_name = str(farmer)[:30] # 시트 이름 길이 제한
                            farmer_data.to_excel(writer, index=False, sheet_name=sheet_name)

                output.seek(0)
                st.download_button(
                    label="📥 최종 발주서 엑셀 다운로드",
                    data=output,
                    file_name='품앗이_스마트발주서.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

    # =========================================================
    # [Tab 2] 마케팅 비서 로직 (새로운 기능)
    # =========================================================
    with tab2:
        st.markdown("### 💡 데이터가 말해주는 '품앗이님'의 마음")
        
        if st.button("🔍 마케팅 전략 분석하기", key="mkt_btn"):
            with st.spinner('장바구니 속 마음을 읽는 중...'):
                
                # 데이터 전처리 (복구된 코드 활용)
                df_mkt = df_sales.copy()
                
                # 컬럼명 확인 및 대응 (POS 파일마다 다를 수 있음)
                req_cols = ['회원', '결제금액', '판매일시', '품목명']
                missing_cols = [c for c in req_cols if c not in df_mkt.columns]
                
                if missing_cols:
                    st.error(f"⚠️ 데이터에 다음 컬럼이 없습니다: {missing_cols}")
                    st.warning("POS 엑셀 파일의 컬럼명을 확인해주세요. (회원, 결제금액, 판매일시, 품목명 필수)")
                else:
                    # 1. 데이터 정제
                    df_member = df_mkt[df_mkt['회원'].notna()].copy() # 비회원 제외
                    df_member['결제금액'] = pd.to_numeric(df_member['결제금액'], errors='coerce').fillna(0)
                    df_member['판매일시'] = pd.to_datetime(df_member['판매일시'])
                    df_member['date'] = df_member['판매일시'].dt.date

                    # ---------------------------------------------------------
                    # [분석 1] 연관 구매 (Market Basket)
                    # ---------------------------------------------------------
                    st.subheader("1. '이거 살 때 저것도 샀다' (연관 구매)")
                    
                    # 상위 50개 품목만 분석 (속도 및 노이즈 제거)
                    top_items = df_member['품목명'].value_counts().head(50).index.tolist()
                    df_top = df_member[df_member['품목명'].isin(top_items)]

                    # 바구니 생성 (같은 사람, 같은 시간)
                    df_top['basket_id'] = df_top['회원'].astype(str) + "_" + df_top['판매일시'].astype(str)
                    baskets = df_top.groupby('basket_id')['품목명'].apply(list)

                    # 쌍(Pair) 찾기
                    item_pairs = Counter()
                    for basket in baskets:
                        if len(basket) > 1:
                            unique_items = sorted(set(basket))
                            for pair in combinations(unique_items, 2):
                                item_pairs[pair] += 1

                    # 시각화 1
                    if item_pairs:
                        top_pairs = item_pairs.most_common(10)
                        df_pairs = pd.DataFrame([{'조합': f"{p[0]} + {p[1]}", '횟수': c} for p, c in top_pairs])
                        
                        fig1, ax1 = plt.subplots(figsize=(10, 6))
                        sns.barplot(data=df_pairs, x='횟수', y='조합', palette='viridis', ax=ax1)
                        ax1.set_title('품앗이 장바구니 베스트 짝꿍 Top 10')
                        st.pyplot(fig1)
                        
                        st.caption("👉 **전략**: 위 조합은 나란히 진열하거나, '두부 살 때 양념장 할인' 같은 묶음 행사를 기획해보세요.")
                    else:
                        st.info("연관 구매 데이터가 충분하지 않습니다.")

                    # ---------------------------------------------------------
                    # [분석 2] 품앗이님 세그먼트 (RFM)
                    # ---------------------------------------------------------
                    st.markdown("---")
                    st.subheader("2. 누가 진짜 주인인가? (충성도 분석)")
                    
                    current_date = df_member['판매일시'].max()
                    rfm = df_member.groupby('회원').agg({
                        '판매일시': lambda x: (current_date - x.max()).days, # Recency
                        'date': 'nunique', # Frequency (방문일수)
                        '결제금액': 'sum' # Monetary
                    }).rename(columns={'판매일시': '최근방문(일전)', 'date': '방문횟수', '결제금액': '총구매액'})

                    # 시각화 2
                    fig2, ax2 = plt.subplots(figsize=(10, 8))
                    sns.scatterplot(
                        data=rfm, x='방문횟수', y='총구매액', 
                        size='총구매액', hue='최근방문(일전)',
                        sizes=(20, 500), alpha=0.6, palette='RdYlGn_r', ax=ax2
                    )
                    
                    # 기준선 (평균)
                    ax2.axvline(rfm['방문횟수'].median(), color='red', linestyle='--', alpha=0.3)
                    ax2.axhline(rfm['총구매액'].median(), color='red', linestyle='--', alpha=0.3)
                    
                    ax2.set_title('품앗이님(조합원) 분포도')
                    ax2.set_xlabel('얼마나 자주 오셨나요? (방문횟수)')
                    ax2.set_ylabel('얼마나 사셨나요? (구매액)')
                    
                    st.pyplot(fig2)
                    st.caption("🟢 **초록색 점**: 최근에 오신 분 | 🔴 **빨간색 점**: 오신 지 오래된 분")
                    st.caption("👉 **오른쪽 위(초록)**에 있는 분들이 '찐 주인(슈퍼단골)'입니다. 이분들께 감사의 문자를 보내세요!")

else:
    st.warning("👈 왼쪽(또는 위)에서 파일 2개를 모두 업로드해주시면 분석 화면이 열립니다.")

