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
    if any('member' in f for f in files):
        st.success("✅ 조합원 명부 파일 있음")
    else:
        st.error("❌ 조합원 명부(member) 파일 없음")

# ==========================================
# 2. [데이터 로드] 헤더 헌팅 로직 (가장 강력함)
# ==========================================
@st.cache_data
def load_smart_data_v6(keyword, type='sales'):
    files = os.listdir('.')
    candidates = [f for f in files if keyword in f]
    
    if not candidates:
        return None, f"'{keyword}' 파일을 찾을 수 없습니다."
    
    real_filename = candidates[0] 

    # 전략: 일단 '헤더 없이' 몽땅 읽어온 뒤, 키워드가 있는 줄을 찾는다.
    df_raw = None
    
    # 1. 파일 읽기 (포맷 무시하고 일단 읽기)
    try:
        # 엑셀로 시도
        df_raw = pd.read_excel(real_filename, header=None, engine='openpyxl')
    except:
        # CSV로 시도 (인코딩 돌려가며)
        for enc in ['utf-8', 'cp949', 'euc-kr']:
            try:
                df_raw = pd.read_csv(real_filename, header=None, encoding=enc, on_bad_lines='skip', engine='python')
                break
            except:
                continue

    if df_raw is None:
        return None, "파일을 열 수 없습니다."

    # 2. '진짜 제목줄' 사냥하기
    # type에 따라 찾아야 할 핵심 단어 정의
    if type == 'sales':
        targets = ['농가', '생산자', '공급자']
    else: # member
        targets = ['회원', '성명', '이름', '조합원']

    target_idx = -1
    
    # 앞부분 50줄을 검사
    for idx, row in df_raw.head(50).iterrows():
        # 한 줄을 문자열로 합침
        row_str = row.astype(str).str.cat(sep=' ')
        # 핵심 단어가 포함되어 있으면 그 줄이 제목이다!
        if any(t in row_str for t in targets):
            target_idx = idx
            break
    
    # 3. 데이터 정리
    if target_idx != -1:
        # 찾은 줄을 제목으로 설정
        df_final = df_raw.iloc[target_idx+1:].copy()
        df_final.columns = df_raw.iloc[target_idx]
    else:
        # 못 찾았으면 그냥 씀
        df_final = df_raw

    # 컬럼 이름 정리 (공백/줄바꿈 제거)
    df_final.columns = df_final.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
    
    # 'Unnamed' 로 시작하는 이상한 컬럼은 삭제 (에러 방지)
    df_final = df_final.loc[:, ~df_final.columns.str.contains('^Unnamed')]
    
    return df_final, None

# 데이터 로드
df_sales, err_sales = load_smart_data_v6('sales_raw', type='sales')
df_member, err_member = load_smart_data_v6('member', type='member')

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
        st.error(f"🚨 판매 데이터 필수 컬럼 누락.\n(현재 인식된 컬럼: {cols})")
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
            
            # 2. 조합원 명부 매칭
            final_phone_col = '연락처'
            
            if df_member is not None and not df_member.empty:
                mem_cols = df_member.columns.tolist()
                
                # 자동 감지 시도
                auto_name = next((c for c in mem_cols if any(x in c for x in ['회원', '성명', '이름', '조합원'])), None)
                auto_phone = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
                
                # [수동 매칭 UI]
                with st.expander("🛠️ 명부 매칭 설정 (클릭해서 확인)", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        # Unnamed가 사라졌는지 확인하세요!
                        sel_name_col = st.selectbox("이름 컬럼 (명부)", mem_cols, index=mem_cols.index(auto_name) if auto_name in mem_cols else 0)
                    with c2:
                        sel_phone_col = st.selectbox("전화번호 컬럼 (명부)", mem_cols, index=mem_cols.index(auto_phone) if auto_phone in mem_cols else 0)
                
                # 매칭 실행 (컬럼이 유효할 때만)
                if sel_name_col and sel_phone_col:
                    # 필요한 컬럼만 딱 잘라서 준비
                    try:
                        phone_book = df_member[[sel_name_col, sel_phone_col]].copy()
                        # 이름이 없는 행 제거, 중복 제거
                        phone_book = phone_book.dropna(subset=[sel_name_col]).drop_duplicates(subset=[sel_name_col])
                        # 문자열로 변환 (매칭 오류 방지)
                        phone_book[sel_name_col] = phone_book[sel_name_col].astype(str)
                        loyal_fans[buyer_col] = loyal_fans[buyer_col].astype(str)
                        
                        # 합치기 (LEFT JOIN)
                        loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=sel_name_col, how='left')
                        loyal_fans.rename(columns={sel_phone_col: final_phone_col}, inplace=True)
                    except Exception as e:
                        st.error(f"매칭 중 오류 발생: {e}")

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
                has_phone = loyal_fans[final_phone_col].notnull().sum() if final_phone_col in loyal_fans.columns else 0
                st.caption(f"📞 연락처 확보: **{has_phone}명**")
                
                display_cols = [buyer_col, '구매횟수']
                if final_phone_col in loyal_fans.columns:
                    display_cols.insert(1, final_phone_col)
                
                st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
                
            with col2:
                st.success("📂 **참여 유도용 파일**")
                buffer = io.BytesIO()
                # 엑셀 엔진 안전 선택
                try:
                    import xlsxwriter
                    engine_name = 'xlsxwriter'
                except:
                    engine_name = 'openpyxl'

                with pd.ExcelWriter(buffer, engine=engine_name) as writer:
                    loyal_fans.to_excel(writer, index=False)
                        
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=buffer,
                    file_name=f"{selected_farmer}_단골.xlsx",
                    mime="application/vnd.ms-excel"
                )
