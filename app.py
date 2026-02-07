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
    
    st.markdown("---")
    st.caption("📂 파일 점검")
    files = os.listdir('.')
    if any('sales_raw' in f for f in files): st.success("✅ 판매 데이터 있음")
    else: st.error("❌ 판매 데이터 없음")
    if any('member' in f for f in files): st.success("✅ 조합원 명부 있음")
    else: st.error("❌ 조합원 명부 없음")

# ==========================================
# 2. [데이터 로드] 스마트 로더
# ==========================================
@st.cache_data
def load_smart_data_v9(keyword, type='sales'):
    files = os.listdir('.')
    candidates = [f for f in files if keyword in f]
    if not candidates: return None, "파일 없음"
    
    candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
    
    for real_filename in candidates:
        try:
            # 헤더 없이 읽기
            try:
                df_raw = pd.read_excel(real_filename, header=None, engine='openpyxl')
            except:
                for enc in ['utf-8', 'cp949', 'euc-kr']:
                    try:
                        df_raw = pd.read_csv(real_filename, header=None, encoding=enc, on_bad_lines='skip', engine='python')
                        if not df_raw.empty: break
                    except: continue
            
            if df_raw is None or df_raw.empty: continue

            # 헤더 찾기
            if type == 'sales':
                targets = ['농가', '생산자', '공급자']
                must_have = ['상품', '품목', '품명', '회원', '구매자'] 
            else: # member
                targets = ['회원', '성명', '이름', '조합원']
                must_have = ['전화', '휴대폰', '연락처', 'HP']

            target_idx = -1
            for idx, row in df_raw.head(50).iterrows():
                row_str = row.astype(str).str.cat(sep=' ')
                if any(t in row_str for t in targets) and any(m in row_str for m in must_have):
                    target_idx = idx
                    break
            
            if target_idx != -1:
                df_final = df_raw.iloc[target_idx+1:].copy()
                df_final.columns = df_raw.iloc[target_idx]
                df_final.columns = df_final.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
                df_final = df_final.loc[:, ~df_final.columns.str.contains('^Unnamed')]
                return df_final, None
        except: continue
    return None, "읽기 실패"

df_sales, err_sales = load_smart_data_v9('sales_raw', type='sales')
df_member, err_member = load_smart_data_v9('member', type='member')

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
        st.error("🚨 판매 데이터 필수 컬럼 누락")
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
            
            # 1. 단골 데이터 추출
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # [강제 생성] 연락처 컬럼을 일단 빈칸으로라도 만듭니다.
            final_phone_col = '연락처'
            loyal_fans[final_phone_col] = "-" 
            
            # 2. 명부 매칭
            if df_member is not None and not df_member.empty:
                mem_cols = df_member.columns.tolist()
                
                auto_name = next((c for c in mem_cols if any(x in c for x in ['회원', '성명', '이름'])), None)
                auto_phone = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
                
                with st.expander("🛠️ 명부 매칭 설정 (클릭)", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        sel_name_col = st.selectbox("이름 컬럼 (명부)", mem_cols, index=mem_cols.index(auto_name) if auto_name in mem_cols else 0)
                    with c2:
                        sel_phone_col = st.selectbox("전화번호 컬럼 (명부)", mem_cols, index=mem_cols.index(auto_phone) if auto_phone in mem_cols else 0)
                    with c3:
                        if sel_name_col:
                            st.write(f"명부 이름 예시: {df_member[sel_name_col].iloc[0]}")
                            st.write(f"판매 이름 예시: {loyal_fans[buyer_col].iloc[0]}")

                if sel_name_col and sel_phone_col:
                    try:
                        # 데이터 준비
                        phone_book = df_member[[sel_name_col, sel_phone_col]].copy()
                        phone_book = phone_book.dropna(subset=[sel_name_col]).drop_duplicates(subset=[sel_name_col])
                        
                        # [핵심] 공백 제거 후 병합
                        phone_book['key_name'] = phone_book[sel_name_col].astype(str).str.strip()
                        loyal_fans['key_name'] = loyal_fans[buyer_col].astype(str).str.strip()
                        
                        merged = pd.merge(loyal_fans, phone_book, on='key_name', how='left')
                        
                        # 연락처 업데이트
                        loyal_fans[final_phone_col] = merged[sel_phone_col].fillna("-")
                        
                    except Exception as e:
                        st.error(f"매칭 중 오류: {e}")

            # ------------------------------------------------
            # 결과 출력 (무조건 연락처 포함)
            # ------------------------------------------------
            st.markdown("---")
            st.subheader(f"
