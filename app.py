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
    
    # 파일 존재 여부 시각적 확인
    sales_exists = any('sales_raw' in f for f in files)
    member_exists = any('member' in f for f in files)
    
    if sales_exists: st.success("✅ 판매 데이터 확인됨")
    else: st.error("❌ 판매 데이터(sales_raw) 없음")
        
    if member_exists: st.success("✅ 조합원 명부 확인됨")
    else: st.warning("⚠️ 조합원 명부(member) 없음")

# ==========================================
# 2. [데이터 로드] 스마트 로더 v7 (가장 강력함)
# ==========================================
@st.cache_data
def load_smart_data_v7(keyword, type='sales'):
    files = os.listdir('.')
    # 키워드가 포함된 모든 파일을 찾습니다.
    candidates = [f for f in files if keyword in f]
    
    if not candidates:
        return None, f"'{keyword}' 관련 파일을 찾을 수 없습니다."
    
    # [핵심] 파일 크기순으로 정렬 (큰 파일이 진짜일 확률 높음)
    candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
    
    # 모든 후보 파일을 순서대로 시도
    for real_filename in candidates:
        try:
            # 1. 일단 '헤더 없이' 몽땅 읽어봅니다. (가장 안전한 방법)
            df_raw = None
            
            # 엑셀로 시도
            try:
                df_raw = pd.read_excel(real_filename, header=None, engine='openpyxl')
            except:
                # CSV로 시도 (인코딩 돌려가며)
                for enc in ['utf-8', 'cp949', 'euc-kr']:
                    try:
                        df_raw = pd.read_csv(real_filename, header=None, encoding=enc, on_bad_lines='skip', engine='python')
                        if not df_raw.empty: break
                    except:
                        continue
            
            if df_raw is None or df_raw.empty:
                continue # 다음 파일 시도

            # 2. '진짜 제목줄' 사냥하기
            if type == 'sales':
                targets = ['농가', '생산자', '공급자']
                # 판매 데이터는 '농가'와 '상품'이 같은 줄에 있어야 진짜 헤더
                must_have = ['상품', '품목', '품명', '회원', '구매자'] 
            else: # member
                targets = ['회원', '성명', '이름', '조합원']
                must_have = ['전화', '휴대폰', '연락처', 'HP']

            target_idx = -1
            
            # 앞부분 50줄을 검사
            for idx, row in df_raw.head(50).iterrows():
                row_str = row.astype(str).str.cat(sep=' ')
                # 핵심 키워드가 포함된 줄 찾기
                # (조건: targets 중 하나 + must_have 중 하나가 동시에 있어야 함 -> 엄격한 검사)
                has_target = any(t in row_str for t in targets)
                has_must = any(m in row_str for m in must_have)
                
                if has_target and has_must:
                    target_idx = idx
                    break
            
            # 3. 데이터 정리
            if target_idx != -1:
                # 찾은 줄을 제목으로 설정
                df_final = df_raw.iloc[target_idx+1:].copy()
                df_final.columns = df_raw.iloc[target_idx]
                
                # 컬럼 이름 정리
                df_final.columns = df_final.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
                
                # 'Unnamed' 컬럼 삭제
                df_final = df_final.loc[:, ~df_final.columns.str.contains('^Unnamed')]
                
                return df_final, None # 성공!
                
        except Exception as e:
            continue # 실패하면 다음 파일로

    return None, "모든 파일 읽기 실패 (파일이 손상되었거나 암호화됨)"

# 데이터 로드
df_sales, err_sales = load_smart_data_v7('sales_raw', type='sales')
df_member, err_member = load_smart_data_v7('member', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패\n이유: {err_sales}")
    st.info("팁: 깃허브에 `sales_raw.xlsx` 파일이 0byte가 아닌지 확인해주세요.")
else:
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    
    if not farmer_col or not buyer_col:
        st.error(f"🚨 판매 데이터 필수 컬럼 누락.\n(현재 인식된 컬럼: {cols})")
    else:
        # 농가 선택 (판매량 순)
        farmer_counts = df_sales[farmer_col].value_counts()
        all_farmers = farmer_counts.index.tolist()
        
        st.info(f"🌾 총 **{len(all_farmers)}**곳의 생산자님이 검색되었습니다.")
        
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
                
                # 자동 감지
                auto_name = next((c for c in mem_cols if any(x in c for x in ['회원', '성명', '이름', '조합원'])), None)
                auto_phone = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
                
                # 매칭 UI
                with st.expander("🛠️ 명부 매칭 확인 (클릭)", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        sel_name_col = st.selectbox("이름 컬럼 (명부)", mem_cols, index=mem_cols.index(auto_name) if auto_name in mem_cols else 0)
                    with c2:
                        sel_phone_col = st.selectbox("전화번호 컬럼 (명부)", mem_cols, index=mem_cols.index(auto_phone) if auto_phone in mem_cols else 0)
                
                # 매칭 실행
                if sel_name_col and sel_phone_col:
                    try:
                        # 명부 데이터 준비
                        phone_book = df_member[[sel_name_col, sel_phone_col]].copy()
                        phone_book = phone_book.dropna(subset=[sel_name_col]).drop_duplicates(subset=[sel_name_col])
                        
                        # 문자열 변환 (매칭 정확도 향상)
                        phone_book[sel_name_col] = phone_book[sel_name_col].astype(str).str.strip()
                        loyal_fans[buyer_col] = loyal_fans[buyer_col].astype(str).str.strip()
                        
                        # 합치기
                        loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=sel_name_col, how='left')
                        loyal_fans.rename(columns={sel_phone_col: final_phone_col}, inplace=True)
                    except Exception as e:
                        st.error(f"매칭 중 오류: {e}")

            # 연락처 미확보 시 판매데이터에서 찾기
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
            st.subheader(f"✅ '{selected_farmer}'님을 아껴주시는 품앗이님들 ({len(loyal_fans)}명)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                # 연락처 확보율
                has_phone = loyal_fans[final_phone_col].notnull().sum() if final_phone_col in loyal_fans.columns else 0
                st.caption(f"📞 연락처 확보: **{has_phone}명**")
                
                display_cols = [buyer_col, '구매횟수']
                if final_phone_col in loyal_fans.columns:
                    display_cols.insert(1, final_phone_col)
                
                st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
                
            with col2:
                st.success("📂 **참여 유도용 파일**")
                st.markdown("이 파일을 다운받아 카카오톡 채널에 업로드하세요.")
                
                buffer = io.BytesIO()
                try:
                    import xlsxwriter
                    engine_name = 'xlsxwriter'
                except:
                    engine_name = 'openpyxl'

                with pd.ExcelWriter(buffer, engine=engine_name) as writer:
                    loyal_fans.to_excel(writer, index=False, sheet_name='품앗이님명단')
                        
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=buffer,
                    file_name=f"{selected_farmer}_단골.xlsx",
                    mime="application/vnd.ms-excel"
                )
