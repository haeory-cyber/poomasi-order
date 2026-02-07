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
    st.caption("📂 파일 점검")
    files = os.listdir('.')
    
    # 파일 존재 여부 표시
    if any('member' in f for f in files):
        st.success("✅ 조합원 명부 파일 있음")
    else:
        st.error("❌ 조합원 명부(member) 파일 없음")

# ==========================================
# 2. [데이터 로드] 스마트 로더
# ==========================================
@st.cache_data
def load_smart_data_v4(keyword, type='sales'):
    files = os.listdir('.')
    candidates = [f for f in files if keyword in f]
    
    if not candidates:
        return None, f"'{keyword}' 파일을 찾을 수 없습니다."
    
    real_filename = candidates[0] 

    # CSV 우선 시도 -> 엑셀 시도
    df = None
    encodings = ['utf-8', 'cp949', 'euc-kr']
    
    # 1. CSV 시도
    for enc in encodings:
        try:
            temp_df = pd.read_csv(real_filename, encoding=enc, on_bad_lines='skip', engine='python')
            
            # 헤더 키워드 (전화번호 관련 단어 대폭 추가)
            if type == 'sales':
                keywords = ['농가', '생산자', '상품', '품목']
            else:
                keywords = ['회원', '성명', '전화', '휴대폰', '연락처', 'HP', '이동전화', '모바일']
            
            target_row = -1
            for idx in range(min(50, len(temp_df))):
                row_str = temp_df.iloc[idx].astype(str).str.cat(sep=' ')
                if sum(k in row_str for k in keywords) >= 2:
                    target_row = idx
                    break
            
            if target_row != -1:
                df = pd.read_csv(real_filename, encoding=enc, header=target_row+1, on_bad_lines='skip', engine='python')
                return clean_columns(df), None
            else:
                return clean_columns(temp_df), None
        except:
            continue

    # 2. 엑셀 시도
    try:
        df = pd.read_excel(real_filename, engine='openpyxl')
        return find_header_and_clean_excel(df, type), None
    except Exception as e:
        return None, f"읽기 실패 ({e})"

def find_header_and_clean_excel(df, type):
    keywords = ['농가', '생산자', '상품', '품목'] if type == 'sales' else ['회원', '성명', '전화', '휴대폰', '연락처']
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

# 데이터 로드
df_sales, err_sales = load_smart_data_v4('sales_raw', type='sales')
df_member, err_member = load_smart_data_v4('member', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {err_sales}")
else:
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    
    if not farmer_col or not buyer_col:
        st.error("🚨 판매 데이터에서 필수 컬럼을 못 찾았습니다.")
    else:
        # 농가 선택
        farmer_counts = df_sales[farmer_col].value_counts()
        all_farmers = farmer_counts.index.tolist()
        
        col_search, col_select = st.columns([1, 2])
        with col_search:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            with col_select:
                selected_farmer = st.selectbox("목록에서 선택", filtered_farmers)
            
            # 데이터 매칭 시작
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # [중요] 조합원 명부 매칭 진단
            final_phone_col = '연락처'
            matched_count = 0
            
            if df_member is not None and not df_member.empty:
                mem_cols = df_member.columns.tolist()
                # 전화번호 관련 키워드 대폭 추가
                phone_keywords = ['전화', '휴대폰', '연락처', 'HP', '이동전화', '모바일', 'Tel']
                name_keywords = ['회원', '성명', '이름', '조합원']
                
                mem_name = next((c for c in mem_cols if any(x in c for x in name_keywords)), None)
                mem_phone = next((c for c in mem_cols if any(x in c for x in phone_keywords)), None)
                
                # 진단 메시지 출력 (화면에 보임)
                if not mem_name or not mem_phone:
                    st.warning(f"⚠️ 명부 파일은 읽었으나 컬럼을 못 찾았습니다.\n(발견된 컬럼: {mem_cols})")
                else:
                    st.success(f"✅ 명부 연결 성공! (이름칸: `{mem_name}`, 전화칸: `{mem_phone}`)")
                    
                    # 매칭 실행
                    phone_book = df_member[[mem_name, mem_phone]].drop_duplicates(subset=[mem_name])
                    loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name, how='left')
                    loyal_fans.rename(columns={mem_phone: final_phone_col}, inplace=True)
                    
                    # 매칭된 숫자 확인
                    matched_count = loyal_fans[final_phone_col].notnull().sum()
            else:
                st.info("ℹ️ 조합원 명부 파일이 없습니다.")

            # 아직도 연락처가 없으면 판매데이터에서 찾기
            if final_phone_col not in loyal_fans.columns:
                sales_phone = next((c for c in cols if any(x in c for x in ['전화', '휴대폰', '연락처'])), None)
                if sales_phone:
                    phones = farmer_df[[buyer_col, sales_phone]].drop_duplicates(subset=[buyer_col], keep='last')
                    loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                    loyal_fans.rename(columns={sales_phone: final_phone_col}, inplace=True)
                else:
                    loyal_fans[final_phone_col] = "번호없음"

            # ------------------------------------------------
            # 결과 출력
            # ------------------------------------------------
            st.markdown("---")
            st.subheader(f"✅ '{selected_farmer}'님 단골 품앗이님 ({len(loyal_fans)}명)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                # 연락처 있는 사람 수 보여주기
                has_phone = loyal_fans[final_phone_col].notnull().sum() if final_phone_col in loyal_fans.columns else 0
                st.caption(f"📞 연락처 확보: {len(loyal_fans)}명 중 **{has_phone}명**")
                
                display_cols = [buyer_col, '구매횟수']
                if final_phone_col in loyal_fans.columns:
                    display_cols.insert(1, final_phone_col)
                
                st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
                
            with col2:
                st.success("📂 **참여 유도용 파일**")
                
                # 엑셀 생성 (xlsxwriter가 없으면 기본값 사용하도록 안전장치)
                buffer = io.BytesIO()
                try:
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        loyal_fans.to_excel(writer, index=False)
                except:
                    # xlsxwriter 없을 때 대비 (fallback)
                    with pd.ExcelWriter(buffer) as writer:
                        loyal_fans.to_excel(writer, index=False)
                        
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=buffer,
                    file_name=f"{selected_farmer}_단골.xlsx",
                    mime="application/vnd.ms-excel"
                )
