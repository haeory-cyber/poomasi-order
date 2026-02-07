import streamlit as st
import pandas as pd

# ==========================================
# 1. [기본 설정] 페이지 및 보안
# ==========================================
st.set_page_config(page_title="품앗이마을 관계망", page_icon="🤝", layout="wide")

# 사이드바: 로그인 및 파일 상태 확인
with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("비밀번호", type="password")
    if password != "poom0118**":
        st.warning("관계자 외 출입금지")
        st.stop()
    
    st.success("환영합니다, 후니님!")
    st.markdown("---")
    st.info("💡 **사용법**\n특정 생산자의 물품이 입고되었을 때, 이전에 구매했던 분들을 찾아 알려주는 도구입니다.")

# ==========================================
# 2. [데이터 로드] 판매 상세 데이터 읽기
# ==========================================
@st.cache_data
def load_data():
    try:
        # sales_raw.xlsx : 누가 무엇을 샀는지 들어있는 '상세' 파일
        # header=0 : 첫 번째 줄을 제목으로 씀
        df = pd.read_excel('sales_raw.xlsx', engine='openpyxl')
        
        # 컬럼 이름 공백 제거 (오류 방지)
        df.columns = df.columns.str.replace(' ', '').str.replace('\n', '')
        return df
    except Exception as e:
        return None

df = load_data()

# ==========================================
# 3. [메인 화면] 단골 매칭 시스템
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")
st.markdown("##### *\"행복한신선농장의 딸기가 입고되었습니다! 누구에게 알려드려야 할까요?\"*")
st.markdown("---")

if df is None:
    st.error("🚨 `sales_raw.xlsx` 파일을 찾을 수 없습니다!")
    st.warning("깃허브(GitHub)에 `sales_raw.xlsx` 파일을 업로드해주세요. (기존 `sales.xlsx` 아님)")
else:
    # ---------------------------------------------------------
    # 1. 생산자 선택하기
    # ---------------------------------------------------------
    st.subheader("1️⃣ 소식을 전할 생산자를 선택하세요")
    
    # '농가명' 또는 '공급자' 컬럼 찾기
    cols = df.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    member_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    item_col = next((c for c in cols if '상품' in c or '품목' in c or '품명' in c), None)
    phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)
    
    if farmer_col and member_col:
        # 농가 목록 추출 (가나다순)
        farmers = sorted(df[farmer_col].dropna().unique().tolist())
        selected_farmer = st.selectbox("어떤 농부님의 소식인가요?", farmers)
        
        # ---------------------------------------------------------
        # 2. 데이터 분석 (단골 찾기)
        # ---------------------------------------------------------
        # 해당 농가의 판매 내역만 필터링
        farmer_df = df[df[farmer_col] == selected_farmer].copy()
        
        # 회원별로 구매 횟수와 총액 집계
        # (회원번호가 있으면 더 정확하겠지만, 일단 이름으로 집계)
        group_cols = [member_col]
        if phone_col: group_cols.append(phone_col)
        
        # 집계 시작
        loyal_fans = farmer_df.groupby(group_cols).size().reset_index(name='구매횟수')
        
        # 내림차순 정렬 (많이 산 순서)
        loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
        
        # ---------------------------------------------------------
        # 3. 결과 보여주기
        # ---------------------------------------------------------
        st.subheader(f"2️⃣ '{selected_farmer}'님을 기다리는 품앗이님들 ({len(loyal_fans)}명)")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.dataframe(
                loyal_fans, 
                use_container_width=True,
                hide_index=True
            )
        with col2:
            st.info("💡 **활용 팁**")
            st.markdown(f"""
            이 분들은 **{selected_farmer}**님의 상품을 
            좋아하시는 찐팬입니다.
            
            입고 문자를 보내면 
            **재방문 확률이 매우 높습니다!**
            """)
            
            # (옵션) 상위 5명만 따로 보기
            top5 = loyal_fans.head(5)[member_col].tolist()
            st.write(f"**🏅 TOP 5 단골:**")
            for fan in top5:
                st.write(f"- {fan} 님")

        # ---------------------------------------------------------
        # 4. 최근 구매 상품 확인 (옵션)
        # ---------------------------------------------------------
        with st.expander("🔎 이분들이 주로 샀던 품목 자세히 보기"):
            if item_col:
                # 품목별 판매량
                top_items = farmer_df[item_col].value_counts().head(5)
                st.bar_chart(top_items)
                st.caption("이 농가에서 가장 인기 있었던 품목들입니다.")

    else:
        st.error("엑셀 파일에서 '농가명'이나 '회원명' 컬럼을 찾을 수 없습니다.")
        st.write("현재 파일의 컬럼들:", cols)
