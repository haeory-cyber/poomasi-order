import streamlit as st
import pandas as pd
import io
import os
import re # 정규표현식 (전화번호 수술 도구)

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
    st.header("📂 데이터 업로드")
    
    st.info("👇 포스 파일(판매내역)을 여기에 넣으세요!")
    uploaded_sales = st.file_uploader("1️⃣ 판매 내역 (직매장...)", type=['xlsx', 'csv'])
    
    st.markdown("---")
    uploaded_member = st.file_uploader("2️⃣ 조합원 명부 (선택사항)", type=['xlsx', 'csv'])
    
    local_files = os.listdir('.')
    local_member = next((f for f in local_files if any(k in f for k in ['member', '조합원', '명부'])), None)
    
    if not uploaded_member and local_member:
        st.caption(f"ℹ️ 서버에 있는 '{local_member}'를 사용합니다.")

# ==========================================
# 2. [데이터 로드] 스마트 업로더
# ==========================================
@st.cache_data
def load_data_from_upload(file_obj, type='sales'):
    if file_obj is None: return None, "파일 없음"
    
    df_raw = None
    try:
        df_raw = pd.read_excel(file_obj, header=None, engine='openpyxl')
    except:
        for enc in ['utf-8', 'cp949', 'euc-kr']:
            try:
                file_obj.seek(0)
                df_raw = pd.read_csv(file_obj, header=None, encoding=enc, on_bad_lines='skip', engine='python')
                if not df_raw.empty: break
            except: continue
    
    if df_raw is None or df_raw.empty: 
        return None, "파일을 읽을 수 없습니다."

    if type == 'sales':
        targets = ['농가', '생산자', '공급자']
        must_have = ['상품', '품목', '품명', '회원', '구매자'] 
    else: 
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
    
    return None, "데이터 형식(헤더)을 찾을 수 없습니다."

# ==========================================
# [데이터 로드 실행]
# ==========================================
if uploaded_sales:
    df_sales, msg_sales = load_data_from_upload(uploaded_sales, 'sales')
else:
    df_sales, msg_sales = None, "파일을 업로드해주세요."

if uploaded_member:
    df_member, msg_member = load_data_from_upload(uploaded_member, 'member')
elif local_member:
    with open(local_member, 'rb') as f:
        file_content = io.BytesIO(f.read())
        df_member, msg_member = load_data_from_upload(file_content, 'member')
else:
    df_member, msg_member = None, "명부 파일이 없습니다."

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if df_sales is None:
    st.info("👈 **왼쪽 사이드바**에서 판매 내역 파일을 업로드해주세요.")
else:
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    
    if not farmer_col or not buyer_name_col:
        st.error("🚨 판매 데이터에서 필수 컬럼(농가명, 회원명)을 찾지 못했습니다.")
    else:
        # 농가 선택
        farmer_counts = df_sales[farmer_col].value_counts()
        all_farmers = farmer_counts.index.tolist()
        
        st.success(f"📊 **{uploaded_sales.name}** 분석 완료! (총 {len(all_farmers)} 농가)")
        
        col_search, col_select = st.columns([1, 2])
        with col_search:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            with col_select:
                selected_farmer = st.selectbox("목록에서 선택", filtered_farmers)
            
            # 1. 판매 데이터 집계
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            group_key = buyer_id_col if buyer_id_col else buyer_name_col
            
            if buyer_id_col:
                loyal_fans = farmer_df.groupby(group_key).agg({buyer_name_col: 'first', group_key: 'count'}).rename(columns={group_key: '구매횟수'}).reset_index()
                loyal_fans['join_key'] = loyal_fans[buyer_id_col].astype(str).str.replace('.0', '').str.strip()
            else:
                loyal_fans = farmer_df.groupby(buyer_name_col).size().reset_index(name='구매횟수')
                loyal_fans['join_key'] = loyal_fans[buyer_name_col].astype(str).str.strip()
            
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            final_phone_col = '연락처'
            
            # 2. 명부 매칭
            if df_member is not None and not df_member.empty:
                mem_cols = df_member.columns.tolist()
                mem_id_auto = next((c for c in mem_cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
                mem_name_auto = next((c for c in mem_cols if any(x in c for x in ['회원명', '성명', '이름'])), None)
                mem_phone_auto = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
                
                with st.expander("🛠️ 명부 매칭 설정", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        match_mode = st.radio("매칭 기준", ["회원번호", "이름"], index=0 if (buyer_id_col and mem_id_auto) else 1)
                    with c2:
                        if "회원번호" in match_mode:
                            sel_key_mem = st.selectbox("명부 회원번호", mem_cols, index=mem_cols.index(mem_id_auto) if mem_id_auto in mem_cols else 0)
                        else:
                            sel_key_mem = st.selectbox("명부 이름", mem_cols, index=mem_cols.index(mem_name_auto) if mem_name_auto in mem_cols else 0)
                    with c3:
                        sel_phone = st.selectbox("명부 전화번호", mem_cols, index=mem_cols.index(mem_phone_auto) if mem_phone_auto in mem_cols else 0)

                if sel_key_mem and sel_phone:
                    try:
                        phone_book = df_member[[sel_key_mem, sel_phone]].copy()
                        def clean_key(x): return str(x).replace('.0', '').strip()
                        phone_book['join_key'] = phone_book[sel_key_mem].apply(clean_key)
                        phone_book = phone_book.drop_duplicates(subset=['join_key'], keep='first')
                        
                        merged = pd.merge(loyal_fans, phone_book[['join_key', sel_phone]], on='join_key', how='left')
                        merged = merged.rename(columns={sel_phone: final_phone_col})
                        merged[final_phone_col] = merged[final_phone_col].fillna("-")
                        loyal_fans = merged
                    except Exception as e:
                        st.error(f"매칭 오류: {e}")
                        loyal_fans[final_phone_col] = "-"
            else:
                 loyal_fans[final_phone_col] = "-"

            # ========================================================
            # 3. [핵심] 전화번호 성형수술 (010-XXXX-XXXX 포맷팅)
            # ========================================================
            def format_phone_number(phone):
                if pd.isna(phone) or phone == '-' or phone == '': return '-'
                # 1. 숫자만 남기기 (010-1234-5678 -> 01012345678)
                clean_num = re.sub(r'[^0-9]', '', str(phone))
                
                # 2. 앞자리 0이 빠진 경우 (1012345678 -> 01012345678)
                if clean_num.startswith('10') and len(clean_num) >= 10:
                    clean_num = '0' + clean_num
                
                # 3. 규격에 맞게 하이픈 넣기
                if len(clean_num) == 11: # 010-1234-5678
                    return f"{clean_num[:3]}-{clean_num[3:7]}-{clean_num[7:]}"
                elif len(clean_num) == 10: 
                    if clean_num.startswith('02'): # 서울 02-1234-5678
                        return f"{clean_num[:2]}-{clean_num[2:6]}-{clean_num[6:]}"
                    else: # 011-123-4567
                        return f"{clean_num[:3]}-{clean_num[3:6]}-{clean_num[6:]}"
                else:
                    return phone # 변환 불가하면 원본 리턴 (확인용)

            # 포맷팅 적용
            if final_phone_col in loyal_fans.columns:
                loyal_fans[final_phone_col] = loyal_fans[final_phone_col].apply(format_phone_number)

            # ========================================================
            # 4. [핵심] 순도 100% 정제 (조합원만 남기기)
            # ========================================================
            
            # A. 엄격 필터링: 연락처 없는 사람(비회원) 제외
            valid_fans = loyal_fans[loyal_fans[final_phone_col] != '-'].copy()
            
            # B. 중복 통합
            if not valid_fans.empty:
                final_df = valid_fans.groupby([buyer_name_col, final_phone_col])['구매횟수'].sum().reset_index()
                final_df = final_df.sort_values(by='구매횟수', ascending=False)
            else:
                final_df = pd.DataFrame(columns=[buyer_name_col, final_phone_col, '구매횟수'])

            # ------------------------------------------------
            # 결과 출력
            # ------------------------------------------------
            st.markdown("---")
            total_cleaned = len(final_df)
            
            st.subheader(f"✅ '{selected_farmer}'님의 진짜 품앗이님 ({total_cleaned}명)")
            
            if total_cleaned > 0:
                st.success(f"✨ 명부와 정확히 일치하는 조합원 **{total_cleaned}명**을 찾았습니다. (전화번호 자동 보정 완료)")
            else:
                st.warning("⚠️ 매칭된 조합원이 없습니다.")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
            with col2:
                st.success("📂 **발송용 명단 다운로드**")
                buffer = io.BytesIO()
                try: import xlsxwriter; engine='xlsxwriter'
                except: engine='openpyxl'
                with pd.ExcelWriter(buffer, engine=engine) as writer:
                    final_df.to_excel(writer, index=False)
                st.download_button("📥 엑셀 받기", data=buffer, file_name=f"{selected_farmer}_조합원명단.xlsx")
