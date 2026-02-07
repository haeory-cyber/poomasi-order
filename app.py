import streamlit as st
import pandas as pd
import os
import io

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
    
    # [진단] 파일 목록 확인
    st.markdown("---")
    st.caption("📂 저장소 파일 현황")
    files = os.listdir('.')
    st.code(files)

# ==========================================
# 2. [데이터 로드] 만능 오프너 (엑셀/CSV 모두 시도)
# ==========================================
@st.cache_data
def load_smart_data(target_name, type='sales'):
    # 1. 파일 이름 찾기 (대소문자 무시)
    current_files = os.listdir('.')
    real_filename = next((f for f in current_files if f.lower() == target_name.lower()), None)
    
    if real_filename is None:
        return None, f"파일 없음 ({target_name})"
    
    # 2. 읽기 시도 (엑셀 -> CSV 순서로)
    df = None
    error_msg = ""
    
    # 전략 A: 엑셀로 읽기 (openpyxl)
    try:
        df = pd.read_excel(real_filename, engine='openpyxl')
    except Exception as e_excel:
        error_msg += f"엑셀 읽기 실패({e_excel}), "
        # 전략 B: CSV로 읽기 (인코딩 바꿔가며 시도)
        try:
            df = pd.read_csv(real_filename, encoding='cp949') # 한글 윈도우 기본
        except:
            try:
                df = pd.read_csv(real_filename, encoding='utf-8')
            except Exception as e_csv:
                error_msg += f"CSV 읽기 실패({e_csv})"

    if df is None:
        return None, error_msg

    # 3. 헤더(제목줄) 찾기
    # 데이터는 읽었으나, 엉뚱한 제목줄이 걸려있을 수 있으므로 진짜 헤더를 찾습니다.
    keywords = []
    if type == 'sales':
        keywords = ['농가', '생산자', '상품', '품목', '공급자']
    elif type == 'member':
        keywords = ['회원', '성명', '전화', '휴대폰', '연락처', '조합원']
        
    target_row = -1
    # 앞부분 20줄 검사
    for idx in range(min(20, len(df))):
        row_str = df.iloc[idx].astype(str).str.cat(sep=' ')
        if sum(k in row_str for k in keywords) >= 2:
            target_row = idx
            break
            
    # 헤더를 찾았으면 다시 깔끔하게 정리
    if target_row != -1:
        # 헤더가 있는 위치(idx)를 기준으로 다시 컬럼 설정
        new_header = df.iloc[target_row] 
        df = df[target_row+1:] 
        df.columns = new_header 

    # 컬럼명 공백 제거
    df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
    return df, None

# 데이터 로드
df_sales, err_sales = load_smart_data('sales_raw.xlsx', type='sales')
df_member, err_member = load_smart_data('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")

# [진단 결과 출력] - 여기가 중요합니다!
if df_sales is None:
    st.error("🚨 판매 데이터 로드 실패!")
    st.warning(f"에러 이유: {err_sales}")
    st.info("팁: 엑셀 파일이 암호화되어 있거나, 확장자가 잘못되었을 수 있습니다.")

elif df_sales is not None:
    # 매칭 및 분석 로직
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    buyer_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    
    # 명부 매칭 준비
    mem_name_col = None
    mem_phone_col = None
    if df_member is not None and not df_member.empty:
        mem_cols = df_member.columns.tolist()
        mem_name_col = next((c for c in mem_cols if '회원' in c or '성명' in c or '이름' in c), None)
        mem_phone_col = next((c for c in mem_cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)
    else:
        df_member = pd.DataFrame() # 빈 데이터프레임

    if farmer_col and buyer_col:
        st.success("✅ 데이터를 성공적으로 읽었습니다!")
        
        all_farmers = sorted(df_sales[farmer_col].dropna().unique().tolist())
        search_query = st.text_input("🔍 농가 이름 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            selected_farmer = st.selectbox("목록에서 선택", filtered_farmers)
            
            # 단골 분석
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # [매칭 로직] 명부에서 전화번호 가져오기
            if not df_member.empty and mem_name_col and mem_phone_col:
                phone_book = df_member[[mem_name_col, mem_phone_col]].drop_duplicates(subset=[mem_name_col])
                loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name_col, how='left')
                final_phone_col = mem_phone_col
            else:
                # 명부 없으면 판매데이터 내 전화번호 사용 시도
                sales_phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c), None)
                if sales_phone_col:
                    phones = farmer_df[[buyer_col, sales_phone_col]].drop_duplicates(subset=[buyer_col], keep='last')
                    loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                    final_phone_col = sales_phone_col
                else:
                    final_phone_col = '연락처없음'
                    loyal_fans[final_phone_col] = '확인불가'

            # 결과 표 출력
            st.markdown("---")
            st.subheader(f"'{selected_farmer}'님의 단골 리스트 ({len(loyal_fans)}명)")
            
            display_cols = [buyer_col, '구매횟수']
            if final_phone_col != '연락처없음':
                display_cols.insert(1, final_phone_col)
            
            st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
            
            # 엑셀 다운로드
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                loyal_fans.to_excel(writer, index=False)
            st.download_button("📥 단골 명단 다운로드", data=buffer, file_name=f"{selected_farmer}_단골.xlsx")
            
    else:
        st.error(f"필수 컬럼을 찾지 못했습니다. (확인된 컬럼: {cols})")
