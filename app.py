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
    
    # 파일 인식 현황 표시
    sales_files = [f for f in files if any(k in f for k in ['sales', '직매장', '판매', '농가별'])]
    member_files = [f for f in files if any(k in f for k in ['member', '조합원', '명부', '회원'])]
    
    if sales_files: st.success(f"✅ 판매 데이터: {len(sales_files)}개 발견")
    else: st.error("❌ 판매 데이터 없음 (키워드: 직매장, 판매, sales)")
        
    if member_files: st.success(f"✅ 조합원 명부: {len(member_files)}개 발견")
    else: st.error("❌ 조합원 명부 없음 (키워드: 조합원, 명부, member)")

# ==========================================
# 2. [데이터 로드] 탱크 로더 (파일명 유연성 강화)
# ==========================================
@st.cache_data
def load_tank_data(keywords, type='sales'):
    files = os.listdir('.')
    # 키워드 중 하나라도 포함된 파일 찾기
    candidates = [f for f in files if any(k in f for k in keywords)]
    
    if not candidates: return None, f"파일을 찾을 수 없습니다. (키워드: {keywords})"
    
    # [업데이트] 파일 선택 기준: 용량이 가장 큰 것 (데이터가 가장 많은 것)
    # 필요하다면 '수정일자' 순으로 바꿀 수도 있습니다.
    candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
    
    for real_filename in candidates:
        try:
            df_raw = None
            # 1. 엑셀/CSV 강제 읽기 (깨진 파일 대응)
            try:
                df_raw = pd.read_excel(real_filename, header=None, engine='openpyxl')
            except:
                for enc in ['utf-8', 'cp949', 'euc-kr']:
                    try:
                        df_raw = pd.read_csv(real_filename, header=None, encoding=enc, on_bad_lines='skip', engine='python')
                        if not df_raw.empty: break
                    except: continue
            
            if df_raw is None or df_raw.empty: continue

            # 2. 진짜 헤더 찾기 (POS 데이터 특성 반영)
            if type == 'sales':
                targets = ['농가', '생산자', '공급자']
                must_have = ['상품', '품목', '품명', '회원', '구매자'] 
            else: 
                targets = ['회원', '성명', '이름', '조합원']
                must_have = ['전화', '휴대폰', '연락처', 'HP']

            target_idx = -1
            for idx, row in df_raw.head(50).iterrows():
                row_str = row.astype(str).str.cat(sep=' ')
                # 키워드가 충분히 포함된 줄을 헤더로 인정
                if any(t in row_str for t in targets) and any(m in row_str for m in must_have):
                    target_idx = idx
                    break
            
            # 3. 데이터 정리
            if target_idx != -1:
                df_final = df_raw.iloc[target_idx+1:].copy()
                df_final.columns = df_raw.iloc[target_idx]
                df_final.columns = df_final.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
                df_final = df_final.loc[:, ~df_final.columns.str.contains('^Unnamed')]
                
                # 파일명도 같이 리턴 (확인용)
                return df_final, real_filename
                
        except: continue
    return None, "모든 파일 읽기 실패"

# 로드 실행 (키워드 대폭 추가)
# 판매데이터: '직매장', '농가별', '판매', 'sales' 등
df_sales, msg_sales = load_tank_data(['sales', '직매장', '판매', '농가별'], type='sales')
# 명부: 'member', '조합원', '명부' 등
df_member, msg_member = load_tank_data(['member', '조합원', '명부', '회원'], type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {msg_sales}")
else:
    # 현재 사용 중인 파일명 표시
    st.info(f"📊 분석 대상 파일: **{msg_sales}** (명부: {msg_member if isinstance(msg_member, str) else '로드 성공'})")
    
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    
    if not farmer_col or not buyer_name_col:
        st.error("🚨 판매 데이터 필수 컬럼(농가, 회원명) 누락")
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
                        # 중복 제거 (첫번째 값 유지)
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
            # 3. [핵심] 순도 100% 정제 (조합원만 남기기)
            # ========================================================
            
            # A. 엄격한 필터링: 연락처가 없는 사람(비회원/유령) 제외
            valid_fans = loyal_fans[loyal_fans[final_phone_col] != '-'].copy()
            
            # B. 중복 통합 (같은 연락처면 하나로 합치기)
            # 이름과 연락처가 같으면 구매횟수 합산
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
                st.success("✨ 조합원 명부와 100% 일치하는 분들만 추려냈습니다.")
            else:
                st.warning("⚠️ 매칭된 조합원이 없습니다. (파일 날짜나 매칭 설정을 확인해주세요)")
            
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
