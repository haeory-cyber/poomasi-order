import streamlit as st
import pandas as pd

# ==========================================
# 1. [보안] 도어락 시스템
# ==========================================
st.set_page_config(page_title="품앗이마을 로컬푸드 2.0", page_icon="🌾", layout="wide")

# 사이드바에서 로그인 처리
with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("조합원 비밀번호를 입력하세요", type="password")
    
    if password != "poom0118**":
        st.warning("비밀번호를 입력해야 입장할 수 있습니다.")
        st.stop()
    
    st.success("환영합니다! 후니님.")
    st.markdown("---")
    st.markdown("**[문의]** 품앗이 생활협동조합")

# ==========================================
# 2. [데이터 로드] 안전하게 읽어오기
# ==========================================
@st.cache_data
def load_data():
    try:
        # engine='openpyxl'을 명시적으로 지정
        df = pd.read_excel('sales.xlsx', engine='openpyxl')
        return df
    except Exception as e:
        # 에러가 나면 화면에 이유를 보여줍니다.
        st.error(f"🚨 데이터 파일 오류: {e}")
        return None

df = load_data()

# ==========================================
# 3. [화면 구성] 로컬푸드 2.0 철학 입히기
# ==========================================

st.title("🌾 품앗이 마을: 농부와 이웃을 잇다")
st.markdown("##### *\"우리는 물건을 파는 것이 아니라, 관계를 잇습니다.\"*")
st.markdown("---")

if df is None:
    st.warning("🚨 데이터를 불러오지 못했습니다. (sales.xlsx 파일이나 내용을 확인해주세요)")
else:
    tab1, tab2, tab3 = st.tabs(["🌱 오늘의 생산자", "🛒 가치 나눔(주문)", "📊 투명한 데이터"])

    with tab1:
        st.subheader("우리 지역 농부님들의 수확")
        st.info("이곳은 가격표 이전에 농부님의 이름을 먼저 기억하는 공간입니다.")
        
        # 컬럼 이름 찾기 시도
        cols = df.columns.astype(str)
        try:
            # 엑셀 파일에 '생산자', '상품', '단가' 같은 단어가 포함된 컬럼을 자동으로 찾습니다.
            name_col = [c for c in cols if '생산자' in c or '농가' in c or '공급자' in c][0]
            item_col = [c for c in cols if '상품' in c or '품명' in c or '품목' in c][0]
            price_col = [c for c in cols if '단가' in c or '매출' in c or '금액' in c][0]
            
            display_df = df[[name_col, item_col, price_col]].head(50)
            
            st.dataframe(
                display_df,
                column_config={
                    name_col: "👩‍🌾 생산자(농장)",
                    item_col: "📦 수확물",
                    price_col: st.column_config.NumberColumn("가치(원)", format="%d원")
                },
                use_container_width=True,
                hide_index=True
            )
        except:
            st.warning("엑셀 파일의 컬럼 이름을 찾기 어렵습니다. 파일을 확인해주세요.")
            st.write("현재 파일의 컬럼명:", cols)

    with tab2:
        st.subheader("가치 소비 참여하기")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("품앗이님 성함 (예: 김성훈)")
        with col2:
            phone = st.text_input("연락처 뒷자리")
            
        if st.button("참여(주문) 목록 확인"):
            if name:
                st.success(f"반갑습니다, {name} 품앗이님! (현재는 조회 기능만 작동합니다)")
            else:
                st.error("성함을 입력해주세요.")

    with tab3:
        st.subheader("데이터 투명성 (Data Transparency)")
        st.write("품앗이 생협은 데이터의 주인이 조합원임을 명시합니다.")
        
        if 'price_col' in locals():
            total_sales = df[price_col].sum()
            st.metric(label="현재까지 이웃과 나눈 총 가치(매출)", value=f"{total_sales:,.0f}원")
