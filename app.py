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
def load_smart_data_final(keyword, type='sales'):
    files = os.listdir('.')
    candidates = [f for f in files if keyword in f]
    if not candidates: return None, "파일 없음"
    
    candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
    
    for real_filename in candidates:
        try:
            # 헤더 없이 읽기 시도
            df_raw = None
            try:
                df_raw = pd.read_excel(real_filename, header=None, engine='openpyxl')
            except:
                for enc in ['utf-8', 'cp949', 'euc-kr']:
                    try:
                        df_raw = pd.read_csv(real_filename, header=None, encoding=enc, on_bad_lines='skip', engine='python')
                        if not df_raw.empty: break
                    except: continue
            
            if df_raw is None or df_raw.empty: continue

            # 헤더 찾기 (키워드 확장)
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
            
            # 데이터 정리
            if target_idx != -1:
                df_final = df_raw.iloc[target_idx+1:].copy()
                df_final.columns = df_raw.iloc[target_idx]
                df_final.columns = df_final.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
                df_final = df_final.loc[:, ~df_final.columns.str.contains('^Unnamed')]
                return df_final, None
        except: continue
    return None, "읽기 실패"

# 데이터 로드
df_sales, err_sales = load_smart_data_final('sales_raw', type='sales')
df_member, err_member = load_smart_data_final('member', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {err_sales}")
else:
    cols = df_sales.columns.tolist()
    
    # 컬럼 자동 감지 (회원번호 추가!)
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    # [핵심] 판매 데이터의 회원번호 컬럼 찾기
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    
    if not farmer_col or not buyer_name_col:
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
            
            # 그룹핑 기준: 회원번호가 있으면 회원번호로, 없으면 이름으로
            group_key = buyer_id_col if buyer_id_col else buyer_name_col
            
            # 구매횟수 집계
            # 이름도 같이 보고 싶으니 agg를 사용
            if buyer_id_col:
                loyal_fans = farmer_df.groupby(group_key).agg({buyer_name_col: 'first', group_key: 'count'}).rename(columns={group_key: '구매횟수'}).reset_index()
                # 컬럼명 정리: 회원번호, 이름, 구매횟수
            else:
                loyal_fans = farmer_df.groupby(buyer_name_col).size().reset_index(name='구매횟수')
            
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # 연락처 컬럼 초기화
            final_phone_col = '연락처'
            loyal_fans[final_phone_col] = "-"
            
            # 2. 명부 매칭 로직 (동명이인 해결)
            if df_member is not None and not df_member.empty:
                mem_cols = df_member.columns.tolist()
                
                # 명부 컬럼 자동 감지
                mem_id_auto = next((c for c in mem_cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
                mem_name_auto = next((c for c in mem_cols if any(x in c for x in ['회원명', '성명', '이름'])), None)
                mem_phone_auto = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
                
                with st.expander("🛠️ 명부 매칭 설정 (동명이인 해결)", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        # 매칭 기준 선택 (회원번호 권장)
                        match_mode = st.radio("매칭 기준", ["회원번호(정확함)", "이름(동명이인 위험)"], index=0 if buyer_id_col and mem_id_auto else 1)
                    
                    with c2:
                        if "회원번호" in match_mode:
                            sel_key_col_mem = st.selectbox("명부의 회원번호 컬럼", mem_cols, index=mem_cols.index(mem_id_auto) if mem_id_auto in mem_cols else 0)
                            key_col_sales = buyer_id_col
                        else:
                            sel_key_col_mem = st.selectbox("명부의 이름 컬럼", mem_cols, index=mem_cols.index(mem_name_auto) if mem_name_auto in mem_cols else 0)
                            key_col_sales = buyer_name_col
                            
                    with c3:
                        sel_phone_col = st.selectbox("명부의 전화번호 컬럼", mem_cols, index=mem_cols.index(mem_phone_auto) if mem_phone_auto in mem_cols else 0)

                    if key_col_sales and sel_key_col_mem:
                        st.caption(f"ℹ️ 판매데이터 '{key_col_sales}' ↔ 명부 '{sel_key_col_mem}' 연결 중...")

                # 매칭 실행
                if sel_key_col_mem and sel_phone_col and key_col_sales:
                    try:
                        # 명부 준비
                        phone_book = df_member[[sel_key_col_mem, sel_phone_col]].copy()
                        # 키값이 없는 경우 제거
                        phone_book = phone_book.dropna(subset=[sel_key_col_mem]).drop_duplicates(subset=[sel_key_col_mem])
                        
                        # 키 통일 (문자열로 변환하여 공백 제거)
                        # 회원번호가 숫자로 되어있을 수 있으니 .0 제거 처리
                        
                        def clean_key(x):
                            return str(x).replace('.0', '').strip()

                        phone_book['join_key'] = phone_book[sel_key_col_mem].apply(clean_key)
                        loyal_fans['join_key'] = loyal_fans[key_col_sales].apply(clean_key)
                        
                        # 병합
                        merged = pd.merge(loyal_fans, phone_book, on='join_key', how='left')
                        
                        # 결과 반영
                        loyal_fans[final_phone_col] = merged[sel_phone_col].fillna("-")
                        
                    except Exception as e:
                        st.error(f"매칭 오류: {e}")

            # ------------------------------------------------
            # 결과 출력
            # ------------------------------------------------
            st.markdown("---")
            st.subheader(f"✅ '{selected_farmer}'님의 단골 ({len(loyal_fans)}명)")
            
            matched_count = (loyal_fans[final_phone_col] != "-").sum()
            if matched_count > 0:
                st.success(f"📞 **{matched_count}명**의 연락처를 찾았습니다! (매칭 기준: {key_col_sales})")
            else:
                st.warning("⚠️ 매칭된 연락처가 없습니다. 매칭 기준을 확인해주세요.")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                # 보여줄 컬럼
                display_cols = [buyer_name_col, final_phone_col, '구매횟수']
                if buyer_id_col: display_cols.insert(1, buyer_id_col) # 회원번호도 같이 보여줌
                
                st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
                
            with col2:
                st.success("📂 **다운로드**")
                buffer = io.BytesIO()
                try: import xlsxwriter; engine='xlsxwriter'
                except: engine='openpyxl'

                with pd.ExcelWriter(buffer, engine=engine) as writer:
                    loyal_fans.to_excel(writer, index=False)
                st.download_button("📥 엑셀 받기", data=buffer, file_name=f"{selected_farmer}_단골.xlsx")
