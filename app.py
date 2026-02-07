import streamlit as st
import pandas as pd
import io
import os
import re # 정규표현식

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
    st.header("📂 데이터 업로드")
    uploaded_sales = st.file_uploader("1️⃣ 판매 내역 (포스 파일)", type=['xlsx', 'csv'])
    st.markdown("---")
    uploaded_member = st.file_uploader("2️⃣ 조합원 명부 (선택사항)", type=['xlsx', 'csv'])
    
    local_files = os.listdir('.')
    local_member = next((f for f in local_files if any(k in f for k in ['member', '조합원', '명부'])), None)
    if not uploaded_member and local_member:
        st.caption(f"ℹ️ 서버 명부 사용: {local_member}")

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
    
    if df_raw is None or df_raw.empty: return None, "읽기 실패"

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
    return None, "헤더 찾기 실패"

# 데이터 로드 실행
if uploaded_sales: df_sales, msg_sales = load_data_from_upload(uploaded_sales, 'sales')
else: df_sales, msg_sales = None, "파일 없음"

if uploaded_member: df_member, msg_member = load_data_from_upload(uploaded_member, 'member')
elif local_member:
    with open(local_member, 'rb') as f:
        file_content = io.BytesIO(f.read())
        df_member, msg_member = load_data_from_upload(file_content, 'member')
else: df_member, msg_member = None, "명부 없음"

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if df_sales is None:
    st.info("👈 왼쪽에서 판매 파일을 업로드해주세요.")
else:
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)

    if not farmer_col or not buyer_name_col:
        st.error("🚨 필수 컬럼 누락")
    else:
        # 1. 농가 선택
        all_farmers = df_sales[farmer_col].value_counts().index.tolist()
        st.success(f"📊 총 {len(all_farmers)} 농가 데이터 분석 완료")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            search_query = st.text_input("🔍 농가 검색", placeholder="농가 이름")
            filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
            selected_farmer = st.selectbox("농가 선택", filtered_farmers)
        
        # 2. 품목 선택
        farmer_df_full = df_sales[df_sales[farmer_col] == selected_farmer].copy()
        with c2:
            if item_col:
                all_items = farmer_df_full[item_col].value_counts().index.tolist()
                item_options = ["전체 상품 보기"] + all_items
                selected_item = st.selectbox("📦 품목 선택", item_options)
            else:
                selected_item = "전체 상품 보기"

        # 3. 데이터 필터링
        if selected_item != "전체 상품 보기":
            target_df = farmer_df_full[farmer_df_full[item_col] == selected_item].copy()
        else:
            target_df = farmer_df_full
            
        # 4. 집계 및 매칭
        group_key = buyer_id_col if buyer_id_col else buyer_name_col
        if buyer_id_col:
            loyal_fans = target_df.groupby(group_key).agg({buyer_name_col: 'first', group_key: 'count'}).rename(columns={group_key: '구매횟수'}).reset_index()
            loyal_fans['join_key'] = loyal_fans[buyer_id_col].astype(str).str.replace('.0', '').str.strip()
        else:
            loyal_fans = target_df.groupby(buyer_name_col).size().reset_index(name='구매횟수')
            loyal_fans['join_key'] = loyal_fans[buyer_name_col].astype(str).str.strip()
        
        loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
        final_phone_col = '연락처'
        
        # 명부 매칭
        if df_member is not None and not df_member.empty:
            mem_cols = df_member.columns.tolist()
            mem_id_auto = next((c for c in mem_cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
            mem_name_auto = next((c for c in mem_cols if any(x in c for x in ['회원명', '성명', '이름'])), None)
            mem_phone_auto = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
            
            with st.expander("🛠️ 명부 매칭 설정", expanded=False):
                mc1, mc2, mc3 = st.columns(3)
                with mc1: match_mode = st.radio("매칭 기준", ["회원번호", "이름"], index=0 if (buyer_id_col and mem_id_auto) else 1)
                with mc2: sel_key_mem = st.selectbox("명부 키 컬럼", mem_cols, index=mem_cols.index(mem_id_auto) if mem_id_auto in mem_cols else 0) if "회원번호" in match_mode else st.selectbox("명부 이름 컬럼", mem_cols, index=mem_cols.index(mem_name_auto) if mem_name_auto in mem_cols else 0)
                with mc3: sel_phone = st.selectbox("명부 전화번호", mem_cols, index=mem_cols.index(mem_phone_auto) if mem_phone_auto in mem_cols else 0)

            if sel_key_mem and sel_phone:
                try:
                    phone_book = df_member[[sel_key_mem, sel_phone]].copy()
                    phone_book['join_key'] = phone_book[sel_key_mem].astype(str).str.replace('.0', '').str.strip()
                    phone_book = phone_book.drop_duplicates(subset=['join_key'], keep='first')
                    merged = pd.merge(loyal_fans, phone_book[['join_key', sel_phone]], on='join_key', how='left')
                    merged = merged.rename(columns={sel_phone: final_phone_col})
                    merged[final_phone_col] = merged[final_phone_col].fillna("-")
                    loyal_fans = merged
                except: loyal_fans[final_phone_col] = "-"
        else: loyal_fans[final_phone_col] = "-"

        # 전화번호 포맷팅 (카카오 규격 010-0000-0000)
        def format_phone(p):
            p = re.sub(r'[^0-9]', '', str(p))
            if p.startswith('10') and len(p)>=10: p = '0'+p
            if len(p)==11: return f"{p[:3]}-{p[3:7]}-{p[7:]}"
            return p if len(p)>5 else "-"
            
        if final_phone_col in loyal_fans.columns:
            loyal_fans[final_phone_col] = loyal_fans[final_phone_col].apply(format_phone)

        # 결과 출력
        valid_fans = loyal_fans[loyal_fans[final_phone_col] != '-'].copy()
        if not valid_fans.empty:
            final_df = valid_fans.groupby([buyer_name_col, final_phone_col])['구매횟수'].sum().reset_index()
            final_df = final_df.sort_values(by='구매횟수', ascending=False)
        else:
            final_df = pd.DataFrame(columns=[buyer_name_col, final_phone_col, '구매횟수'])

        st.markdown("---")
        st.subheader(f"✅ '{selected_farmer}' - '{selected_item}' 구매 품앗이님 ({len(final_df)}명)")
        
        # [핵심] 엑셀 다운로드 버튼 분리
        col_down1, col_down2 = st.columns(2)
        
        # 1. 일반 분석용 파일
        with col_down1:
            buffer1 = io.BytesIO()
            with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer: final_df.to_excel(writer, index=False)
            st.download_button("📥 분석용 엑셀 (상세)", data=buffer1, file_name=f"{selected_farmer}_{selected_item}_상세.xlsx")
            
        # 2. 카카오 업로드 전용 파일 (컬럼명 변경: 이름, 전화번호)
        with col_down2:
            kakao_df = final_df[[buyer_name_col, final_phone_col]].copy()
            # 카카오가 좋아하는 컬럼명으로 강제 변경
            kakao_df.columns = ['이름', '전화번호'] 
            
            buffer2 = io.BytesIO()
            with pd.ExcelWriter(buffer2, engine='xlsxwriter') as writer: 
                kakao_df.to_excel(writer, index=False)
            
            st.download_button("🟡 **카카오 업로드용** (바로 올리세요)", data=buffer2, file_name=f"{selected_farmer}_카카오업로드용.xlsx")

        # 미리보기
        st.caption("👇 분석 결과 미리보기")
        st.dataframe(final_df, use_container_width=True, hide_index=True)
