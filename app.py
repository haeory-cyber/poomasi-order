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
    if password != "poom0118**":
        st.warning("비밀번호를 입력해주세요.")
        st.stop()
    st.success("환영합니다, 후니님!")
    st.info("💡 **사용법**\n생산자를 검색하고 [카톡 발송용 파일]을 다운로드하세요.")
    
    # 파일 목록 진단 (보조용)
    st.markdown("---")
    st.caption("📂 저장소 파일 현황")
    st.code(os.listdir('.'))

# ==========================================
# 2. [핵심] 만능 데이터 로더 (절대 실패하지 않음)
# ==========================================
@st.cache_data
def load_smart_data(target_name, type='sales'):
    # 1. 파일 찾기 (대소문자 무시)
    files = os.listdir('.')
    real_filename = next((f for f in files if f.lower() == target_name.lower()), None)
    
    if not real_filename:
        return None, "파일 없음"

    # 2. 일단 무조건 읽기 (엑셀 -> CSV utf-8 -> CSV cp949 순서)
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
    
    # 3. '진짜 제목줄' 찾기 (데이터 정제)
    # 데이터는 읽었지만, 엉뚱한 결재란/제목이 포함되어 있을 수 있음
    if df is not None:
        keywords = []
        if type == 'sales':
            keywords = ['농가', '생산자', '상품', '품목', '공급자']
        elif type == 'member':
            keywords = ['회원', '성명', '전화', '휴대폰', '연락처', '조합원']
            
        target_row = -1
        # 앞부분 30줄을 뒤져서 키워드가 2개 이상 나오면 그 줄이 헤더!
        for idx in range(min(30, len(df))):
            row_str = df.iloc[idx].astype(str).str.cat(sep=' ')
            if sum(k in row_str for k in keywords) >= 2:
                target_row = idx
                break
        
        # 헤더 정리
        if target_row != -1:
            new_header = df.iloc[target_row]
            df = df[target_row+1:]
            df.columns = new_header
            
        # 컬럼명 공백 제거 (오류 방지)
        df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
        
        return df, None
        
    return None, "알 수 없는 오류"

# 데이터 로드 실행
df_sales, err_sales = load_smart_data('sales_raw.xlsx', type='sales')
df_member, err_member = load_smart_data('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면] 로직 구현
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")

# 에러 메시지 처리
if df_sales is None:
    st.error("🚨 판매 데이터를 읽지 못했습니다.")
    st.write(f"이유: {err_sales}")
else:
    # -----------------------------------------------------
    # A. 컬럼 자동 매칭
    # -----------------------------------------------------
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    buyer_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    item_col = next((c for c in cols if '상품' in c or '품목' in c or '품명' in c), None)
    
    # 명부 컬럼 매칭
    mem_name_col = None
    mem_phone_col = None
    if df_member is not None and not df_member.empty:
        mem_cols = df_member.columns.tolist()
        mem_name_col = next((c for c in mem_cols if '회원' in c or '성명' in c or '이름' in c), None)
        mem_phone_col = next((c for c in mem_cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)

    # -----------------------------------------------------
    # B. 검색 및 분석 인터페이스
    # -----------------------------------------------------
    if farmer_col and buyer_col:
        # 1. 생산자 검색
        st.subheader("1️⃣ 소식을 전할 생산자를 검색하세요")
        all_farmers = sorted(df_sales[farmer_col].dropna().unique().tolist())
        
        col_search, col_select = st.columns([1, 2])
        with col_search:
            search_query = st.text_input("🔍 이름 검색 (예: 행복)", placeholder="농가명 입력")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            with col_select:
                selected_farmer = st.selectbox("목록에서 선택", filtered_farmers)
            
            # 2. 데이터 분석 (단골 추출)
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            # 구매 횟수 집계
            loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # 3. 연락처 매칭 (VLOOKUP 로직)
            final_phone_col = '연락처'
            
            # (1순위) 조합원 명부에서 찾기
            if mem_name_col and mem_phone_col:
                phone_book = df_member[[mem_name_col, mem_phone_col]].drop_duplicates(subset=[mem_name_col])
                loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name_col, how='left')
                loyal_fans.rename(columns={mem_phone_col: final_phone_col}, inplace=True)
            else:
                # (2순위) 판매 데이터 내 연락처 사용
                sales_phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c), None)
