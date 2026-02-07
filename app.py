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
    st.caption("📂 파일 진단")
    files = os.listdir('.')
    # 파일 목록 보여주기 (디버깅용)
    st.code(files)

# ==========================================
# 2. [데이터 로드] 탱크 로더 (무조건 읽음)
# ==========================================
@st.cache_data
def load_tank_data(keyword, type='sales'):
    files = os.listdir('.')
    candidates = [f for f in files if keyword in f]
    
    if not candidates:
        return None, f"파일 없음 (키워드: {keyword})"
    
    # 가장 큰 파일 선택
    candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
    target_file = candidates[0]
    
    # 1단계: CSV 강제 읽기 (깨진 줄 무시)
    # 인코딩 3대장 시도
    for enc in ['utf-8', 'cp949', 'euc-kr']:
        try:
            # on_bad_lines='skip': 에러나는 줄은 쿨하게 패스
            # engine='python': 좀 더 튼튼한 엔진 사용
            df = pd.read_csv(target_file, encoding=enc, on_bad_lines='skip', engine='python')
            
            # 읽기 성공! 이제 제목줄 찾기
            return find_header_tank(df, type), None
        except:
            continue
            
    # 2단계: 그래도 안 되면 엑셀로 읽기
    try:
        df = pd.read_excel(target_file, engine='openpyxl')
        return find_header_tank(df, type), None
    except Exception as e:
        return None, f"최종 실패: {e}"

def find_header_tank(df, type):
    # 빈 데이터면 리턴
    if df.empty: return df

    # 1. 키워드로 찾기
    if type == 'sales':
        keywords = ['농가', '생산자', '상품', '품목', '공급자']
    else:
        keywords = ['회원', '성명', '이름', '조합원', '전화']

    best_idx = -1
    for idx, row in df.head(30).iterrows():
        row_str = row.astype(str).str.cat(sep=' ')
        if sum(1 for k in keywords if k in row_str) >= 2:
            best_idx = idx
            break
            
    # 2. 못 찾으면 강제 지정 (아까 분석한 위치)
    if best_idx == -1:
        if type == 'sales': best_idx = 7 # 판매데이터는 보통 8번째 줄
        else: best_idx = 2 # 명부는 보통 3번째 줄
    
    # 헤더 적용
    df_new = df.iloc[best_idx+1:].copy()
    df_new.columns = df.iloc[best_idx]
    
    # 컬럼 청소
    df_new.columns = df_new.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
    df_new = df_new.loc[:, ~df_new.columns.str.contains('^Unnamed')]
    
    return df_new

# 데이터 로드 시도
df_sales, err_sales = load_tank_data('sales_raw', type='sales')
df_member, err_member = load_tank_data('member', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

# 에러 진단 메시지 출력
if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패!")
    st.code(err_sales) # 에러 내용 그대로 보여줌
else:
    # 성공 시 로직
    cols = df_sales.columns.tolist()
    
    # 컬럼 자동 감지 (회원번호 필수)
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    
    if not farmer_col:
        st.error(f"🚨 판매데이터에서 '농가명' 컬럼을 못 찾았습니다. (인식된 컬럼: {cols})")
    elif not buyer_name_col:
        st.error(f"🚨 판매데이터에서 '구매자명' 컬럼을 못 찾았습니다. (인식된 컬럼: {cols})")
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
            
            # 분석 시작
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            
            # 그룹핑 (회원번호 있으면 그걸로, 없으면 이름으로)
            group_key = buyer_id_col if buyer_id_col else buyer_name_col
            
            if buyer_id_col:
                # 회원번호 기준 집계 (이름은 대표값 하나만 가져옴)
                loyal_fans = farmer_df.groupby(group_key).agg({buyer_name_col: 'first', group_key: 'count'}).rename(columns={group_key: '구매횟수'}).reset_index()
            else:
                loyal_fans = farmer_df.groupby(buyer_name_col).size().reset_index(name='구매횟수')
            
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # 연락처 컬럼 준비
            final_phone_col = '연락처'
            loyal_fans[final_phone_col] = "-"
            
            # --- 명부 매칭 ---
            if df_member is not None and not df_member.empty:
                mem_cols = df_member.columns.tolist()
                
                # 명부 컬럼 자동 감지
                mem_id_auto = next((c for c in mem_cols if any(x in c for x in ['회원번호', '조합원번호'])), None)
                mem_name_auto = next((c for c in mem_cols if any(x in c for x in ['회원명', '성명', '이름'])), None)
                mem_phone_auto = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
                
                with st.expander("🛠️ 명부 매칭 설정 (동명이인 해결)", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        # 매칭 기준 선택
                        match_mode = st.radio("매칭 기준", ["회원번호(강력추천)", "이름"], index=0 if (buyer_id_col and mem_id_auto) else 1)
                    
                    with c2:
                        if "회원번호" in match_mode:
                            if not buyer_id_col: st.error("판매데이터에 '회원번호'가 없습니다.")
                            sel_key_sales = buyer_id_col
                            sel_key_mem = st.selectbox("명부 회원번호 컬럼", mem_cols, index=mem_cols.index(mem_id_auto) if mem_id_auto in mem_cols else 0)
                        else:
                            sel_key_sales = buyer_name_col
                            sel_key_mem = st.selectbox("명부 이름 컬럼", mem_cols, index=mem_cols.index(mem_name_auto) if mem_name_auto in mem_cols else 0)
                            
                    with c3:
                        sel_phone = st.selectbox("명부 전화번호 컬럼", mem_cols, index=mem_cols.index(mem_phone_auto) if mem_phone_auto in mem_cols else 0)

                # 매칭 실행
                if sel_key_sales and sel_key_mem and sel_phone:
                    try:
                        # 키 정제 함수 (소수점 제거, 공백 제거)
                        def clean_key(x):
                            return str(x).replace('.0', '').strip()

                        # 명부 준비
                        phone_book = df_member[[sel_key_mem, sel_phone]].copy()
                        phone_book = phone_book.dropna(subset=[sel_key_mem]).drop_duplicates(subset=[sel_key_mem])
                        phone_book['join_key'] = phone_book[sel_key_mem].apply(clean_key)
                        
                        # 판매데이터 키 준비
                        loyal_fans['join_key'] = loyal_fans[sel_key_sales].apply(clean_key)
                        
                        # 병합
                        merged = pd.merge(loyal_fans, phone_book, on='join_key', how='left')
                        loyal_fans[final_phone_col] = merged[sel_phone].fillna("-")
                        
                    except Exception as e:
                        st.error(f"매칭 중 에러: {e}")

            # --- 결과 출력 ---
            st.markdown("---")
            matched_cnt = (loyal_fans[final_phone_col] != "-").sum()
            st.subheader(f"✅ '{selected_farmer}'님의 단골 ({len(loyal_fans)}명)")
            
            if matched_cnt > 0:
                st.success(f"📞 **{matched_cnt}명** 연락처 확보 성공! (기준: {match_mode})")
            else:
                st.warning("⚠️ 연락처가 매칭되지 않았습니다. 매칭 기준을 확인해주세요.")

            c1, c2 = st.columns([2, 1])
            with c1:
                # 보여줄 컬럼
                cols_to_show = [buyer_name_col, final_phone_col, '구매횟수']
                if buyer_id_col: cols_to_show.insert(1, buyer_id_col)
                st.dataframe(loyal_fans[cols_to_show], use_container_width=True, hide_index=True)
                
            with c2:
                st.success("📂 **다운로드**")
                buffer = io.BytesIO()
                try: import xlsxwriter; engine='xlsxwriter'
                except: engine='openpyxl'
                with pd.ExcelWriter(buffer, engine=engine) as writer:
                    loyal_fans.to_excel(writer, index=False)
                st.download_button("📥 엑셀 받기", data=buffer, file_name=f"{selected_farmer}_단골.xlsx")
