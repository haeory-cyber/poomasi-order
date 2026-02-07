import streamlit as st
import pandas as pd

# ==========================================
# 1. [기본 설정]
# ==========================================
st.set_page_config(page_title="품앗이마을 관계망", page_icon="🤝", layout="wide")

with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("비밀번호", type="password")
    if password != "poom0118**":
        st.warning("관계자 외 출입금지")
        st.stop()
    st.success("환영합니다, 후니님!")
    st.info("💡 **사용법**\n검색창에 생산자 이름을 입력하면 해당 농가를 빠르게 찾을 수 있습니다.")

# ==========================================
# 2. [데이터 로드] 스마트 헤더 찾기
# ==========================================
@st.cache_data
def load_data():
    file_name = 'sales_raw.xlsx'
    try:
        # 제목줄 찾기 로직
        temp_df = pd.read_excel(file_name, header=None, nrows=20, engine='openpyxl')
        target_row = -1
        for idx, row in temp_df.iterrows():
            row_str = row.astype(str).str.cat(sep=' ')
            if ('농가' in row_str or '생산자' in row_str) and ('상품' in row_str or '품목' in row_str):
                target_row = idx
                break
        
        if target_row != -1:
            df = pd.read_excel(file_name, header=target_row, engine='openpyxl')
            df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
            return df
        else:
            return pd.read_excel(file_name, engine='openpyxl')
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return None

df = load_data()

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")
st.markdown("##### *\"농부님의 땀을 기억하는 단골손님을 찾아드립니다.\"*")
st.markdown("---")

if df is None:
    st.error("🚨 `sales_raw.xlsx` 파일을 찾을 수 없습니다.")
else:
    # 컬럼 자동 찾기
    cols = df.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    member_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    item_col = next((c for c in cols if '상품' in c or '품목' in c or '품명' in c), None)
    phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)

    if farmer_col and member_col:
        # -----------------------------------------------------
        # [NEW] 검색 기능 추가
        # -----------------------------------------------------
        st.subheader("1️⃣ 소식을 전할 생산자를 찾아보세요")
        
        # 전체 농가 리스트 가져오기
        all_farmers = sorted(df[farmer_col].dropna().unique().tolist())
        
        # 검색창 만들기
        search_query = st.text_input("🔍 농가 이름 검색 (예: 행복, 유기농)", placeholder="찾으시는 농가 이름을 입력하세요")
        
        # 검색어에 따라 목록 필터링
        if search_query:
            filtered_farmers = [f for f in all_farmers if search_query in str(f)]
        else:
            filtered_farmers = all_farmers
            
        # 선택 상자 (필터링된 목록만 보여줌)
        if filtered_farmers:
            selected_farmer = st.selectbox("목록에서 선택해주세요", filtered_farmers)
            
            # -----------------------------------------------------
            # 분석 및 결과 출력
            # -----------------------------------------------------
            farmer_df = df[df[farmer_col] == selected_farmer].copy()
            
            # 단골 집계
            group_cols = [member_col]
            if phone_col: group_cols.append(phone_col)
            
            loyal_fans = farmer_df.groupby(group_cols).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            st.markdown("---")
            st.subheader(f"2️⃣ '{selected_farmer}'님의 단골 품앗이님 ({len(loyal_fans)}명)")
            
            col1, col2 = st.columns([3, 2])
            with col1:
                st.write(f"구매 횟수가 많은 순서대로 정렬했습니다.")
                st.dataframe(loyal_fans, use_container_width=True, hide_index=True)
                
            with col2:
                # [꿀팁] 문자 메시지용 텍스트 생성
                st.info("📢 **문자 발송용 명단** (복사해서 쓰세요)")
                
                # 상위 20명 전화번호만 추출 (전화번호 컬럼이 있을 때)
                if phone_col:
                    phones = loyal_fans.head(20)[phone_col].astype(str).tolist()
                    phones_str = ", ".join(phones)
                    st.text_area("상위 20명 전화번호", phones_str, height=100)
                else:
                    names = loyal_fans.head(20)[member_col].astype(str).tolist()
                    st.text_area("상위 20명 이름", ", ".join(names), height=100)

            # 인기 상품 분석
            if item_col:
                with st.expander(f"🔎 {selected_farmer}님의 효자 상품은?"):
                    top_items = farmer_df[item_col].value_counts().head(5)
                    st.bar_chart(top_items)
                    
        else:
            st.warning("검색 결과가 없습니다. 이름을 다시 확인해주세요.")
            
    else:
        st.error("엑셀 파일에서 필요한 컬럼(농가명, 회원명)을 찾지 못했습니다.")
