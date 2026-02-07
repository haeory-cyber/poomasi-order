import streamlit as st
import pandas as pd
import io
import os
import re
import time
import hmac
import hashlib
import uuid
import datetime
import requests

# ==========================================
# 0. [내장함수] 쿨에스엠에스 직접 연결
# ==========================================
def send_coolsms_direct(api_key, api_secret, sender, receiver, text):
    try:
        date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        salt = str(uuid.uuid4())
        data = date + salt
        signature = hmac.new(api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {
            "Authorization": f"HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}",
            "Content-Type": "application/json"
        }
        url = "https://api.coolsms.co.kr/messages/v4/send"
        payload = {"message": {"to": receiver, "from": sender, "text": text}}
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200: return True, res.json()
        else: return False, res.json()
    except Exception as e: return False, str(e)

def clean_phone_number(phone):
    if pd.isna(phone) or phone == '-' or phone == '': return '-'
    clean_num = re.sub(r'[^0-9]', '', str(phone))
    if clean_num.startswith('10') and len(clean_num) >= 10: clean_num = '0' + clean_num
    return clean_num 

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
    st.header("⚙️ 쿨에스엠에스 설정")
    api_key = st.text_input("API Key", type="password", placeholder="NCS...")
    api_secret = st.text_input("API Secret", type="password", placeholder="CCPY...")
    sender_number = st.text_input("발신번호 (하이픈 없이)", placeholder="01012345678")
    
    st.markdown("---")
    st.header("📂 데이터 업로드")
    uploaded_sales = st.file_uploader("1️⃣ 판매 내역 (포스 파일)", type=['xlsx', 'csv'])
    uploaded_member = st.file_uploader("2️⃣ 조합원 명부 (필수)", type=['xlsx', 'csv'])
    
    local_files = os.listdir('.')
    local_member = next((f for f in local_files if any(k in f for k in ['member', '조합원', '명부'])), None)
    if not uploaded_member and local_member:
        st.caption(f"ℹ️ 서버 명부 사용: {local_member}")

# ==========================================
# 2. [데이터 로드]
# ==========================================
@st.cache_data
def load_data_from_upload(file_obj, type='sales'):
    if file_obj is None: return None, "파일 없음"
    df_raw = None
    try: df_raw = pd.read_excel(file_obj, header=None, engine='openpyxl')
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

# ==========================================
# 3. [메인 로직]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

# 데이터 로딩
if uploaded_sales: df_sales, msg_sales = load_data_from_upload(uploaded_sales, 'sales')
else: df_sales, msg_sales = None, "파일 없음"

if uploaded_member: df_member, msg_member = load_data_from_upload(uploaded_member, 'member')
elif local_member:
    with open(local_member, 'rb') as f:
        file_content = io.BytesIO(f.read())
        df_member, msg_member = load_data_from_upload(file_content, 'member')
else: df_member, msg_member = None, "명부 없음"


# === [모드 선택] ===
mode = st.radio("👉 작업 모드를 선택하세요:", ["🛒 판매 데이터로 찾기 (마케팅)", "🔍 이름으로 직접 찾기 (개별 발송)"], horizontal=True)

final_df = pd.DataFrame() # 결과 담을 그릇
sender_name_default = "" # 문자 보낼 때 쓸 기본 이름

# ------------------------------------------------
# [모드 1] 판매 데이터 기반 (기존 기능)
# ------------------------------------------------
if "판매 데이터" in mode:
    if df_sales is None:
        st.info("👈 **왼쪽 사이드바**에서 [판매 내역] 파일을 먼저 업로드해주세요.")
    else:
        # (기존 로직 수행)
        cols = df_sales.columns.tolist()
        farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
        buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
        buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
        item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)

        if not farmer_col or not buyer_name_col:
            st.error("🚨 판매 내역 파일 형식을 확인할 수 없습니다.")
        else:
            all_farmers = df_sales[farmer_col].value_counts().index.tolist()
            c1, c2 = st.columns([1, 1])
            with c1:
                search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
                filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
                selected_farmer = st.selectbox("농가 선택", filtered_farmers)
                sender_name_default = selected_farmer # 문자 발송시 농가 이름 기본값
            
            farmer_df_full = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            with c2:
                if item_col:
                    all_items = farmer_df_full[item_col].value_counts().index.tolist()
                    item_options = ["전체 상품 보기"] + all_items
                    selected_item = st.selectbox("📦 품목 선택", item_options)
                else: selected_item = "전체 상품 보기"

            if selected_item != "전체 상품 보기":
                target_df = farmer_df_full[farmer_df_full[item_col] == selected_item].copy()
            else: target_df = farmer_df_full

            # 집계
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
                
                # 자동 매칭 시도
                sel_key_mem = mem_id_auto if (buyer_id_col and mem_id_auto) else mem_name_auto
                sel_phone = mem_phone_auto

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

            # 최종 정리
            if final_phone_col in loyal_fans.columns:
                loyal_fans['clean_phone'] = loyal_fans[final_phone_col].apply(clean_phone_number)
            
            valid_fans = loyal_fans[(loyal_fans['clean_phone'] != '-') & (loyal_fans['clean_phone'].str.len() >= 10)].copy()
            if not valid_fans.empty:
                final_df = valid_fans.groupby([buyer_name_col, 'clean_phone'])['구매횟수'].sum().reset_index()
                final_df = final_df.sort_values(by='구매횟수', ascending=False)
                # 컬럼명 통일 (이름, 전화번호, 비고)
                final_df.columns = ['이름', '전화번호', '비고(구매횟수)']

# ------------------------------------------------
# [모드 2] 이름 검색 (신규 기능)
# ------------------------------------------------
else:
    if df_member is None:
        st.info("👈 **왼쪽 사이드바**에서 [조합원 명부] 파일을 업로드해야 검색할 수 있습니다.")
    else:
        st.subheader("🔍 전체 명부에서 검색")
        
        mem_cols = df_member.columns.tolist()
        mem_name_col = next((c for c in mem_cols if any(x in c for x in ['회원명', '성명', '이름'])), None)
        mem_phone_col = next((c for c in mem_cols if any(x in c for x in ['휴대전화', '전화', '연락처', 'HP'])), None)
        
        if not mem_name_col or not mem_phone_col:
            st.error("명부 파일에서 '이름'과 '전화번호' 컬럼을 찾을 수 없습니다.")
        else:
            # 검색창
            search_keyword = st.text_input("찾을 이름이나 전화번호를 입력하세요 (빈칸이면 전체 조회)", placeholder="예: 김성훈")
            
            # 데이터 준비
            df_search = df_member[[mem_name_col, mem_phone_col]].copy()
            df_search.columns = ['이름', '전화번호']
            df_search['전화번호'] = df_search['전화번호'].apply(clean_phone_number)
            
            # 검색 필터
            if search_keyword:
                mask = df_search['이름'].astype(str).str.contains(search_keyword) | df_search['전화번호'].astype(str).str.contains(search_keyword)
                filtered_result = df_search[mask]
            else:
                filtered_result = df_search.head(100) # 검색어 없으면 상위 100명만
                if not search_keyword: st.caption("입력하지 않으면 상위 100명만 보여줍니다.")

            if not filtered_result.empty:
                filtered_result['비고(선택)'] = "직접선택"
                final_df = filtered_result
                sender_name_default = "품앗이마을" # 기본 발송자 이름
            else:
                st.warning("검색 결과가 없습니다.")

# ------------------------------------------------
# [공통] 결과 출력 및 발송 인터페이스
# ------------------------------------------------
st.markdown("---")

if not final_df.empty:
    st.subheader(f"✅ 대상자 선택 ({len(final_df)}명)")
    
    # 1. 체크박스 UI (공통)
    final_df.insert(0, "발송", True) # 기본 체크
    
    edited_df = st.data_editor(
        final_df,
        column_config={
            "발송": st.column_config.CheckboxColumn("선택", default=True),
            "전화번호": st.column_config.TextColumn("전화번호"),
        },
        disabled=["이름", "전화번호", "비고"],
        hide_index=True,
        use_container_width=True
    )
    
    # 선택된 사람만 추출
    selected_df = edited_df[edited_df['발송'] == True].drop(columns=['발송'])
    
    st.write(f"👉 **총 {len(selected_df)}명 선택됨**")

    # 탭 구성
    tab1, tab2 = st.tabs(["📊 엑셀 다운로드", "🚀 문자 발송"])
    
    with tab1:
        if len(selected_df) > 0:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: selected_df.to_excel(writer, index=False)
            st.download_button("📥 선택 명단 다운로드 (Excel)", data=buffer, file_name="선택명단.xlsx")
        else:
            st.warning("선택된 사람이 없습니다.")

    with tab2:
        st.subheader(f"🚀 메시지 작성 ({len(selected_df)}명)")
        
        if not api_key or not api_secret or not sender_number:
            st.error("👈 왼쪽 사이드바에 'API Key' 등을 입력해주세요!")
        elif len(selected_df) == 0:
            st.warning("발송할 대상이 없습니다.")
        else:
            col_msg, col_preview = st.columns([1, 1])
            with col_msg:
                msg_content = st.text_area("💌 메시지 내용", height=150,
                                           placeholder=f"안녕하세요, {sender_name_default}입니다.")
                st.info(f"📤 **발신번호:** {sender_number}")

            with col_preview:
                st.markdown("#### 📱 미리보기")
                st.code(msg_content if msg_content else "(내용을 입력하세요)")
                st.warning(f"💰 예상 비용: 약 **{len(selected_df) * 20:,}원**")

            st.markdown("---")
            send_col1, send_col2 = st.columns([1, 3])
            
            with send_col1:
                test_phone = st.text_input("테스트 발송 번호", placeholder="01012345678")
                if st.button("내 폰으로 테스트"):
                    if not test_phone: st.error("번호를 입력하세요.")
                    else:
                        success, res = send_coolsms_direct(api_key, api_secret, sender_number, test_phone, msg_content)
                        if success: st.success("✅ 전송 성공!")
                        else: st.error(f"❌ 전송 실패: {res}")

            with send_col2:
                st.write("") 
                st.write("") 
                if st.button(f"🚀 **선택한 {len(selected_df)}명에게 발송**", type="primary"):
                    if not msg_content:
                        st.error("내용을 입력하세요!")
                    else:
                        progress_bar = st.progress(0)
                        targets = selected_df['전화번호'].tolist()
                        success_cnt = 0
                        for i, phone in enumerate(targets):
                            time.sleep(0.1)
                            suc, _ = send_coolsms_direct(api_key, api_secret, sender_number, phone, msg_content)
                            if suc: success_cnt += 1
                            progress_bar.progress((i + 1) / len(targets))
                        st.success(f"🎉 **총 {success_cnt}건 발송 성공!**")
                        st.balloons()
else:
    if "판매 데이터" in mode and df_sales is not None:
         st.warning("조건에 맞는 구매자가 없습니다.")
    elif "이름으로" in mode and df_member is not None:
         pass # 검색 전 대기
