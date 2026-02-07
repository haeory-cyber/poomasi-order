import streamlit as st
import pandas as pd
import io
import os
import csv

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
    st.markdown("---")
    st.caption("📂 저장소 파일 현황")
    st.code(os.listdir('.'))

# ==========================================
# 2. [핵심] 절대 실패하지 않는 데이터 로더
# ==========================================
@st.cache_data
def load_smart_data_v2(target_name, type='sales'):
    files = os.listdir('.')
    real_filename = next((f for f in files if f.lower() == target_name.lower()), None)
    
    if not real_filename: return None, "파일 없음"

    # A. 엑셀(xlsx)로 시도
    try:
        df = pd.read_excel(real_filename, engine='openpyxl')
        return find_header_and_clean(df, type), None
    except:
        pass

    # B. CSV(텍스트)로 시도 - 한 줄씩 읽어서 헤더 찾기 (ParserError 방지)
    encodings = ['utf-8', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            # 파일을 텍스트로 엽니다 (표로 읽지 않음)
            with open(real_filename, 'r', encoding=enc) as f:
                lines = f.readlines()
            
            # 헤더 키워드 정의
            keywords = []
            if type == 'sales':
                keywords = ['농가', '생산자', '상품', '품목', '공급자']
            elif type == 'member':
                keywords = ['회원', '성명', '전화', '휴대폰', '연락처', '조합원', '이름']
            
            # 텍스트 줄을 훑으며 헤더 위치 찾기
            header_row_idx = -1
            for i, line in enumerate(lines[:50]): # 앞 50줄만 검사
                if sum(k in line for k in keywords) >= 2:
                    header_row_idx = i
                    break
            
            if header_row_idx != -1:
                # 헤더 위치를 찾았으면, 거기서부터 다시 DataFrame으로 읽음
                # on_bad_lines='skip': 칸 수 안 맞는 줄은 건너뜀 (중요!)
                df = pd.read_csv(real_filename, encoding=enc, header=header_row_idx, on_bad_lines='skip')
                return clean_columns(df), None
            else:
                # 헤더를 못 찾았으면 그냥 읽음
                df = pd.read_csv(real_filename, encoding=enc, on_bad_lines='skip')
                return clean_columns(df), None
                
        except Exception as e:
            continue # 다음 인코딩 시도

    return None, "모든 방식으로 읽기 실패 (파일이 손상되었거나 암호화됨)"

def find_header_and_clean(df, type):
    # 이미 DataFrame으로 읽힌 상태에서 헤더 찾기
    keywords = ['농가', '생산자', '상품', '품목'] if type == 'sales' else ['회원', '성명', '전화']
    
    target_row = -1
    for idx in range(min(30, len(df))):
        row_str = df.iloc[idx].astype(str).str.cat(sep=' ')
        if sum(k in row_str for k in keywords) >= 2:
            target_row = idx
            break
            
    if target_row != -1:
        new_header = df.iloc[target_row]
        df = df[target_row+1:]
        df.columns = new_header
        
    return clean_columns(df)

def clean_columns(df):
    df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
    return df

# 데이터 로드 실행
df_sales, err_sales = load_smart_data_v2('sales_raw.xlsx', type='sales')
df_member, err_member = load_smart_data_v2('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {err_sales}")
    st.info("팁: 엑셀 파일을 열어서 '다른 이름으로 저장' > 'CSV(쉼표로 분리)' 형식으로 저장해서 올려보세요.")
else:
    cols = df_sales.columns.tolist()
    
    # 컬럼 자동 매칭
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '주문자', '소비자', '이름'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)
    
    st.info(f"📊 **데이터 분석 상태** (농가 컬럼: `{farmer_col}` / 구매자 컬럼: `{buyer_col}`)")

    if not farmer_col or not buyer_col:
        st.error("🚨 필수 컬럼(농가명, 구매자명)을 찾지 못했습니다.")
        st.write("인식된 컬럼들:", cols)
    else:
        # 1. 판매량 많은 순으로 농가 정렬
        farmer_counts = df_sales[farmer_col].value_counts()
        all_farmers = farmer_counts.index.tolist()
        
        st.write(f"🌾 총 **{len(all_farmers)}**곳의 생산자가 검색되었습니다.")
        
        col_search, col_select = st.columns([1, 2])
        with col_search:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            with col_select:
                selected_farmer = st.selectbox("목록에서 선택하세요 (판매량 많은 순)", filtered_farmers)
            
            # 분석 시작
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            
            if farmer_df.empty:
                st.warning("데이터 없음")
            else:
                # 단골 집계
                loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
                loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
                
                # 명부 매칭
                final_phone_col = '연락처'
                if df_member is not None and not df_member.empty:
                    mem_cols = df_member.columns.tolist()
                    mem_name = next((c for c in mem_cols if any(x in c for x in ['회원', '성명', '이름'])), None)
                    mem_phone = next((c for c in mem_cols if any(x in c for x in ['전화', '핸드폰', '연락처'])), None)
                    
                    if mem_name and mem_phone:
                        phone_book = df_member[[mem_name, mem_phone]].drop_duplicates(subset=[mem_name])
                        loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name, how='left')
                        loyal_fans.rename(columns={mem_phone: final_phone_col}, inplace=True)
                
                # 연락처 없으면 판매데이터에서 찾기
                if final_phone_col not in loyal_fans.columns:
                    sales_phone = next((c for c in cols if any(x in c for x in ['전화', '핸드폰', '연락처'])), None)
                    if sales_phone:
                        phones = farmer_df[[buyer_col, sales_phone]].drop_duplicates(subset=[buyer_col], keep='last')
                        loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                        loyal_fans.rename(columns={sales
