import streamlit as st
import pandas as pd
import io
import os
import re

# ==========================================
# 1. [기본 설정]
# ==========================================
st.set_page_config(page_title="품앗이마을 관계망", page_icon="🤝", layout="wide")

# 사이드바 (로그인 & 파일 업로드)
with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("비밀번호", type="password")
    if password != "poom0118**":
        st.warning("비밀번호를 입력해주세요.")
        st.stop()
    st.success("환영합니다, 후니님!")
    
    st.markdown("---")
    st.header("📂 데이터 업로드")
    
    # 1. 판매 파일 업로드
    st.info("👇 포스 파일(판매내역)을 여기에 넣으세요!")
    uploaded_sales = st.file_uploader("1️⃣ 판매 내역 (직매장...)", type=['xlsx', 'csv'])
    
    st.markdown("---")
    
    # 2. 명부 파일 업로드
    uploaded_member = st.file_uploader("2️⃣ 조합원 명부 (선택사항)", type=['xlsx', 'csv'])
    
    # 서버에 저장된 명부 파일 찾기 (업로드 안 했을 때용)
    local_files = os.listdir('.')
    local_member = next((f for f in local_files if any(k in f for k in ['member', '조합원', '명부'])), None)
    
    if not uploaded_member and local_member:
        st.caption(f"ℹ️ 서버에 있는 '{local_member}'를 사용합니다.")

# ==========================================
# 2. [데이터 로드] 스마트 읽기 도구
# ==========================================
@st.cache_data
def load_data_from_upload(file_obj, type='sales'):
    if file_obj is None: return None, "파일 없음"
    
    df_raw = None
    # 1. 엑셀/CSV 강제 읽기
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

    # 2. 헤더(제목줄) 찾기
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
    
    # 3. 데이터프레임 정리
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
# 판매 데이터
if uploaded_sales:
    df_sales, msg_sales = load_data_from_upload(uploaded_sales, 'sales')
else:
    df_sales, msg_sales = None, "파일을 업로드해주세요."

# 명부 데이터
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
    
    # 필수 컬럼 감지
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)
    
    if not farmer_col or not buyer_name_col:
        st.error("🚨 판매 데이터에서 필수 컬럼(농가명, 회원명)을 찾지 못했습니다.")
    else:
        # 1. 농가 선택
        farmer_counts = df_sales[farmer_col].value_counts()
        all_farmers = farmer_counts.index.tolist()
        
        st.success(f"📊 **{uploaded_sales.name}** 분석 완료! (총 {len(all_farmers)} 농가)")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
            filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
            selected_farmer = st.selectbox("농가 선택", filtered_farmers)
            
        # 2. 품목 선택 (옵션)
        farmer_df_full = df_sales[df_sales[farmer_col] == selected_farmer].copy()
        
        with col2:
            if item_col:
                all_items = farmer_df_full[item_col].value_counts().index.tolist()
                item_options = ["전체 상품 보기"] + all_items
                selected_item = st.selectbox("📦 품목 선택", item_options)
            else:
                selected_item = "전체 상품 보기"

        # 데이터 필터링
        if selected_item != "전체 상품 보기":
            target_df = farmer_df_full[farmer_df_full[item_col] == selected_item].copy()
        else:
            target_df = farmer_df_full

        # 3. 집계 (회원번호 기준 우선)
        group_key = buyer_id_col if buyer_id_col else buyer_name_col
        
        if buyer_id_col:
            loyal_fans = target_df.groupby(group_key).agg({buyer_name_col: 'first', group_key: 'count'}).rename(columns={group_key: '구매횟수'}).reset_index()
            loyal_fans['join_key'] = loyal_fans[buyer_id_col].astype(str).str.replace('.0', '').str.strip()
        else:
            loyal_fans = target_df.groupby(buyer_name_col).size().reset_index(name='구매횟수')
            loyal_fans['join_key'] = loyal_fans[buyer_name_col].astype(str).str.strip()
        
        loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
        final_phone_col = '연락처'
        
        # 4. 명부 매칭
        if df_member is not None and not df_member.empty:
            mem_cols = df_member.columns.tolist()
            mem_id_auto = next((c for c in mem_cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
            mem_name_auto = next((c for c in mem_cols if any(x in c for x in ['회원명', '성명', '이름'])), None)
            mem_phone_auto = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
            
            with st.expander("🛠️ 명부 매칭 설정 (필요시 클릭)", expanded=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    match_mode = st.radio("매칭 기준", ["회원번호", "이름"], index=0 if (buyer_id_col and mem_id_auto) else 1)
                with c2:
                    if "회원번호" in match_mode:
                        sel_key_mem = st.selectbox("명부 키 컬럼", mem_cols, index=mem_cols.index(mem_id_auto) if mem_id_auto in mem_cols else 0)
                    else:
                        sel_key_mem = st.selectbox("명부 이름 컬럼", mem_cols, index=mem_cols.index(mem_name_auto) if mem_name_auto in mem_cols else 0)
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
                except:
                    loyal_fans[final_phone_col] = "-"
        else:
             loyal_fans[final_phone_col] = "-"

        # 5. 전화번호 성형수술 (010-0000-0000)
        def format_phone_number(phone):
            if pd.isna(phone) or phone == '-' or phone == '': return '-'
            clean_num = re.sub(r'[^0-9]', '', str(phone))
            if clean_num.startswith('10') and len(clean_num) >= 10: clean_num = '0' + clean_num
            
            if len(clean_num) == 11: 
                return f"{clean_num[:3]}-{clean_num[3:7]}-{clean_num[7:]}"
            elif len(clean_num) == 10: 
                if clean_num.startswith('02'): return f"{clean_num[:2]}-{clean_num[2:6]}-{clean_num[6:]}"
                else: return f"{clean_num[:3]}-{clean_num[3:6]}-{clean_num[6:]}"
            else: return phone

        if final_phone_col in loyal_fans.columns:
            loyal_fans[final_phone_col] = loyal_fans[final_phone_col].apply(format_phone_number)

        # 6. 유령 제거 및 중복 통합
        valid_fans = loyal_fans[loyal_fans[final_phone_col] != '-'].copy()
        
        if not valid_fans.empty:
            final_df = valid_fans.groupby([buyer_name_col, final_phone_col])['구매횟수'].sum().reset_index()
            final_df = final_df.sort_values(by='구매횟수', ascending=False)
        else:
            final_df = pd.DataFrame(columns=[buyer_name_col, final_phone_col, '구매횟수'])

        # ------------------------------------------------
        # 결과 출력 & 다운로드 버튼 3종
        # ------------------------------------------------
        st.markdown("---")
        st.subheader(f"✅ '{selected_farmer}' - '{selected_item}' 구매 품앗이님 ({len(final_df)}명)")
        
        if len(final_df) > 0:
            st.caption("👇 아래 버튼을 눌러 용도에 맞는 파일을 받으세요.")
            
            # 버튼 3개를 가로로 배치
            btn1, btn2, btn3 = st.columns(3)
            
            with btn1:
                # 1. 일반 분석용
                buffer1 = io.BytesIO()
                with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer: final_df.to_excel(writer, index=False)
                st.download_button("📥 **분석용** (상세)", data=buffer1, file_name=f"{selected_farmer}_상세명단.xlsx")
            
            with btn2:
                # 2. 카카오용 (이름, 전화번호)
                kakao_df = final_df[[buyer_name_col, final_phone_col]].copy()
                kakao_df.columns = ['이름', '전화번호'] 
                buffer2 = io.BytesIO()
                with pd.ExcelWriter(buffer2, engine='xlsxwriter') as writer: kakao_df.to_excel(writer, index=False)
                st.download_button("🟡 **카카오톡** 업로드용", data=buffer2, file_name=f"{selected_farmer}_카카오용.xlsx")

            with btn3:
                # 3. 행복ICT 문자용 (이름, 휴대폰번호)
                sms_df = final_df[[buyer_name_col, final_phone_col]].copy()
                sms_df.columns = ['이름', '휴대폰번호'] 
                buffer3 = io.BytesIO()
                with pd.ExcelWriter(buffer3, engine='xlsxwriter') as writer: sms_df.to_excel(writer, index=False)
                st.download_button("🟢 **문자(행복ICT)** 업로드용", data=buffer3, file_name=f"{selected_farmer}_행복ICT용.xlsx")

        else:
            st.warning("⚠️ 조건에 맞는 명단이 없습니다.")
            
        # 미리보기 표
        st.dataframe(final_df, use_container_width=True, hide_index=True)
