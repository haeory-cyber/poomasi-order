import streamlit as st
import pandas as pd
import io
import os

# ==========================================
# 1. [기본 설정]
# ==========================================
st.set_page_config(page_title="품앗이마을 관계망", page_icon="🤝", layout="wide")

with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("비밀번호", type="password")
    if password != "poomasi2026":
        st.warning("비밀번호를 입력해주세요.")
        st.stop()
    st.success("환영합니다, 후니님!")
    st.markdown("---")
    st.caption("📂 저장소 파일 현황")
    st.code(os.listdir('.'))

# ==========================================
# 2. [데이터 로드] 만능 로더
# ==========================================
@st.cache_data
def load_smart_data(target_name, type='sales'):
    files = os.listdir('.')
    real_filename = next((f for f in files if f.lower() == target_name.lower()), None)
    
    if not real_filename: return None, "파일 없음"

    df = None
    try:
        df = pd.read_excel(real_filename, engine='openpyxl')
    except:
        try:
            df = pd.read_csv(real_filename, encoding='utf-8')
        except:
            try:
                df = pd.read_csv(real_filename, encoding='cp949')
            except Exception as e:
                return None, f"읽기 실패: {e}"
    
    if df is not None:
        # 헤더 찾기 (키워드 확장)
        keywords = []
        if type == 'sales':
            keywords = ['농가', '생산자', '상품', '품목', '공급자']
        elif type == 'member':
            keywords = ['회원', '성명', '전화', '휴대폰', '연락처', '조합원', '이름']
            
        target_row = -1
        # 데이터 앞부분 30줄을 검사
        for idx in range(min(30, len(df))):
            row_str = df.iloc[idx].astype(str).str.cat(sep=' ')
            if sum(k in row_str for k in keywords) >= 2:
                target_row = idx
                break
        
        if target_row != -1:
            new_header = df.iloc[target_row]
            df = df[target_row+1:]
            df.columns = new_header
            
        # 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
        return df, None
        
    return None, "알 수 없는 오류"

# 데이터 로드
df_sales, err_sales = load_smart_data('sales_raw.xlsx', type='sales')
df_member, err_member = load_smart_data('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {err_sales}")
else:
    # -----------------------------------------------------
    # [진단] 컬럼 매칭 상태 보여주기
    # -----------------------------------------------------
    cols = df_sales.columns.tolist()
    
    # 컬럼 찾기 (키워드 매칭)
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '주문자', '소비자', '이름'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)
    
    st.info(f"📊 **데이터 분석 상태**\n- 농가 컬럼: `{farmer_col}`\n- 구매자 컬럼: `{buyer_col}`")

    if not farmer_col or not buyer_col:
        st.error("🚨 엑셀 파일에서 '농가명'이나 '구매자명'을 찾지 못했습니다.")
        st.write("현재 엑셀 파일의 컬럼들:", cols)
        st.warning("팁: 엑셀 파일의 제목줄에 '농가명', '회원명' 같은 단어가 있는지 확인해주세요.")
    else:
        # 정상 작동
        all_farmers = sorted(df_sales[farmer_col].dropna().unique().tolist())
        
        col_search, col_select = st.columns([1, 2])
        with col_search:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            with col_select:
                selected_farmer = st.selectbox("목록에서 선택하세요", filtered_farmers)
            
            # 분석 시작
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            
            if farmer_df.empty:
                st.warning("선택한 농가의 판매 데이터가 없습니다.")
            else:
                # 단골 집계
                loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
                loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
                
                # 명부
