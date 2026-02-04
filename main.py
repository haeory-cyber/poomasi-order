import streamlit as st
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from collections import Counter
import os
import matplotlib.font_manager as fm

# ---------------------------------------------------------
# [기본 설정] 폰트 및 페이지 디자인
# ---------------------------------------------------------
st.set_page_config(page_title="슬기로운 품앗이생활", page_icon="🌱", layout="wide")

# 한글 폰트 설정
def set_korean_font():
    if os.name == 'posix':
        plt.rc('font', family='NanumGothic')
    else:
        plt.rc('font', family='Malgun Gothic')
    plt.rcParams['axes.unicode_minus'] = False

set_korean_font()

# 메인 타이틀 (대문)
st.title("슬기로운 품앗이생활 🌱")
st.markdown("### 데이터로 만드는 우리들의 협동조합")

# ---------------------------------------------------------
# [공통] 파일 업로드 섹션
# ---------------------------------------------------------
st.info("💡 **매입처 기준표**와 **POS 판매 데이터**를 업로드하면, 우리 매장의 '생활 기록부'가 펼쳐집니다.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. 기준표 (체크리스트)")
    uploaded_file_standard = st.file_uploader("★매입처_체크리스트.xlsx 파일을 올려주세요", type=['xlsx'])

with col2:
    st.subheader("2. 판매 데이터 (POS)")
    uploaded_file_sales = st.file_uploader("직매장 판매내역 엑셀(행복ICT)을 올려주세요", type=['xlsx', 'csv'])

# ---------------------------------------------------------
# [탭 설정] 업무 공간 분리 (이름 변경!)
# ---------------------------------------------------------
# 여기가 핵심입니다! 탭 이름을 바꿨습니다.
tab1, tab2 = st.tabs(["🛒 슬기로운 발주생활", "📈 슬기로운 마케팅생활"])

# 데이터가 둘 다 있을 때만 작동
if uploaded_file_standard and uploaded_file_sales:
    
    # 데이터 로드
    df_std = pd.read_excel(uploaded_file_standard)
    
    if uploaded_file_sales.name.endswith('.csv'):
        df_sales = pd.read_csv(uploaded_file_sales)
    else:
        df_sales = pd.read_excel(uploaded_file_sales)

    # =========================================================
    # [Tab 1] 슬기로운 발주생활
    # =========================================================
    with tab1:
        st.markdown("### 📋 품절 없는 매장을 위한 똑똑한 주문")
        
        if st.button("🚀 발주 분석 시작하기", key="order_btn"):
            with st.spinner('데이터를 분석 중입니다...'):
                # 컬럼명 처리
                sales_cols = df_sales.columns
                item_col = '품목명' if '품목명' in sales_cols else '상품명'
                qty_col = '수량'
                amt_col = '결제금액' if '결제금액' in sales_cols else '합계'

                # 데이터 집계
                sales_summary = df_sales.groupby(item_col)[[qty_col, amt_col]].sum().reset_index()
                sales_summary.rename(columns={item_col: '품목명', qty_col: '총판매수량', amt_col: '총판매금액'}, inplace=True)
                
                # 판매건수(인기) 집계
                sales_count = df_sales[item_col].value_counts().reset_index()
                sales_count.columns = ['품목명', '판매건수(인기)']
                
                final_sales = pd.merge(sales_summary, sales_count, on='품목명', how='left')
                merged_df = pd.merge(df_std, final_sales, on='품목명', how='left')

                merged_df['총판매수량'] = merged_df['총판매수량'].fillna(0)
                merged_df['판매건수(인기)'] = merged_df['판매건수(인기)'].fillna(0)

                result_df = merged_df.sort_values(by='판매건수(인기)', ascending=False)

                st.success(f"✅ 분석 완료! 총 {len(result_df)}개 품목이 발주 대상입니다.")
                st.write("🏆 **품앗이님들이 가장 많이 찾은 Top 5**")
                st.dataframe(result_df[['농가명', '품목명', '판매건수(인기)', '총판매수량']].head(5))

                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    result_df.to_excel(writer, index=False, sheet_name='전체발주권고')
                    farmers = result_df['농가명'].unique()
                    for farmer in farmers:
                        if pd.isna(farmer): continue
                        farmer_data = result_df[result_df['농가명'] == farmer]
                        if farmer_data['판매건수(인기)'].sum() > 0: 
                            sheet_name = str(farmer)[:30]
                            farmer_data.to_excel(writer, index=False, sheet_name=sheet_name)

                output.seek(0)
                st.download_button(
                    label="📥 최종 발주서 엑셀 다운로드",
                    data=output,
                    file_name='품앗이_스마트발주서.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

    # =========================================================
    # [Tab 2] 슬기로운 마케팅생활
    # =========================================================
    with tab2:
        st.markdown("### 💡 주인의 마음을 읽는 데이터 전략")
        
        if st.button("🔍 마케팅 전략 분석하기", key="mkt_btn"):
            with st.spinner('장바구니 속 이야기를 읽는 중...'):
                df_mkt = df_sales.copy()
                req_cols = ['회원', '결제금액', '판매일시', '품목명']
                missing_cols = [c for c in req_cols if c not in df_mkt.columns]
                
                if missing_cols:
                    st.error(f"⚠️ 데이터 컬럼 부족: {missing_cols}")
                else:
                    df_member = df_mkt[df_mkt['회원'].notna()].copy()
                    df_member['결제금액'] = pd.to_numeric(df_member['결제금액'], errors='coerce').fillna(0)
                    df_member['판매일시'] = pd.to_datetime(df_member['판매일시'])
                    df_member['date'] = df_member['판매일시'].dt.date

                    st.subheader("1. 짝꿍 상품 분석 (연관 구매)")
                    top_items = df_member['품목명'].value_counts().head(50).index.tolist()
                    df_top = df_member[df_member['품목명'].isin(top_items)]
                    df_top['basket_id'] = df_top['회원'].astype(str) + "_" + df_top['판매일시'].astype(str)
                    baskets = df_top.groupby('basket_id')['품목명'].apply(list)

                    item_pairs = Counter()
                    for basket in baskets:
                        if len(basket) > 1:
                            unique_items = sorted(set(basket))
                            for pair in combinations(unique_items, 2):
                                item_pairs[pair] += 1

                    if item_pairs:
                        top_pairs = item_pairs.most_common(10)
                        df_pairs = pd.DataFrame([{'조합': f"{p[0]} + {p[1]}", '횟수': c} for p, c in top_pairs])
                        fig1, ax1 = plt.subplots(figsize=(10, 6))
                        sns.barplot(data=df_pairs, x='횟수', y='조합', palette='viridis', ax=ax1)
                        ax1.set_title('함께 많이 팔린 짝꿍 상품 Top 10')
                        st.pyplot(fig1)
                    else:
                        st.info("데이터가 부족합니다.")

                    st.markdown("---")
                    st.subheader("2. 단골(주인) 분포도")
                    current_date = df_member['판매일시'].max()
                    rfm = df_member.groupby('회원').agg({
                        '판매일시': lambda x: (current_date - x.max()).days,
                        'date': 'nunique',
                        '결제금액': 'sum'
                    }).rename(columns={'판매일시': '최근방문(일전)', 'date': '방문횟수', '결제금액': '총구매액'})

                    fig2, ax2 = plt.subplots(figsize=(10, 8))
                    sns.scatterplot(
                        data=rfm, x='방문횟수', y='총구매액', 
                        size='총구매액', hue='최근방문(일전)',
                        sizes=(20, 500), alpha=0.6, palette='RdYlGn_r', ax=ax2
                    )
                    ax2.axvline(rfm['방문횟수'].median(), color='red', linestyle='--', alpha=0.3)
                    ax2.axhline(rfm['총구매액'].median(), color='red', linestyle='--', alpha=0.3)
                    ax2.set_title('품앗이님 활동 분포 (RFM)')
                    st.pyplot(fig2)

else:
    st.warning("👈 파일을 업로드해주세요.")
