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
    
    st.subheader("1. 마케팅용 (판매데이터)")
    uploaded_sales = st.file_uploader("포스 판매내역 업로드", type=['xlsx', 'csv'], key='sales')
    
    st.subheader("2. 검색/전체발송용 (명부)")
    uploaded_member = st.file_uploader("👉 '회원관리(최신전체).xlsx' 업로드", type=['xlsx', 'csv'], key='member')

# ==========================================
# 2. [데이터 로드] - 로직 단순화 (헤더 자동탐색 제거)
# ==========================================
@st.cache_data
def load_data_from_upload(file_obj, type='sales'):
    if file_obj is None: return None, "파일 없음"
    df_raw = None
    try: df_raw = pd.read_excel(file_obj, engine='openpyxl') # 헤더 자동 (1행)
    except:
        try: df_raw = pd.read_csv(file_obj, encoding='utf-8')
        except: 
            try: df_raw = pd.read_csv(file_obj, encoding='cp949')
            except: return None, "읽기 실패"
    return df_raw, None

# ==========================================
# 3. [메인 로직]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

# 데이터 로딩
df_sales, msg_sales = load_data_from_upload(uploaded_sales, 'sales')
df_member, msg_member = load_data_from_upload(uploaded_member, 'member')

# === [모드 선택] ===
mode = st.radio("👉 작업 모드를 선택하세요:", ["🛒 판매 데이터로 마케팅 (단골 찾기)", "🔍 전체 명부 검색 (개별 발송)"], horizontal=True)

final_df = pd.DataFrame() 
sender_name_default = "" 

# ------------------------------------------------
# [모드 1] 판매 데이터 기반
# ------------------------------------------------
if "판매 데이터" in mode:
    if df_sales is None:
        st.info("👈 **왼쪽 사이드바** 1번에 [판매 내역] 파일을 업로드해주세요.")
    else:
        # 컬럼 자동 찾기 (여기는 기존 유지)
        cols = df_sales.columns.tolist()
        farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
        buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
        item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)

        if not farmer_col or not buyer_name_col:
            st.error("🚨 판매 내역 형식을 인식할 수 없습니다. (헤더가 1행에 있나요?)")
            st.write("감지된 컬럼들:", cols)
        else:
            all_farmers = df_sales[farmer_col].value_counts().index.tolist()
            c1, c2 = st.columns([1, 1])
            with c1:
                search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
                filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
                selected_farmer = st.selectbox("농가 선택", filtered_farmers)
                sender_name_default = selected_farmer
            
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
            loyal_fans = target_df.groupby(buyer_name_col).size().reset_index(name='구매횟수')
            loyal_fans['join_key'] = loyal_fans[buyer_name_col].astype(str).str.strip()
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # [수정] 명부 매칭 로직 보강
            final_phone_col = '연락처'
            if df_member is not None:
                # 명부 컬럼 수동 선택 가능하게 (Expander)
                with st.expander("🛠️ 명부 매칭 설정 (전화번호가 안 뜨면 클릭)", expanded=False):
                    m_cols = df_member.columns.tolist()
                    st.write("현재 명부 컬럼:", m_cols)
                    # 자동 추천
                    auto_name = next((c for c in m_cols if any(x in c for x in ['회원명', '성명', '이름'])), m_cols[0])
                    auto_phone = next((c for c in m_cols if any(x in c for x in ['휴대전화', '전화', '연락처'])), m_cols[-1])
                    
                    sel_name = st.selectbox("명부에서 '이름' 컬럼 선택", m_cols, index=m_cols.index(auto_name))
                    sel_phone = st.selectbox("명부에서 '전화번호' 컬럼 선택", m_cols, index=m_cols.index(auto_phone))

                if sel_name and sel_phone:
                    phone_book = df_member[[sel_name, sel_phone]].copy()
                    phone_book.columns = ['join_key', final_phone_col]
                    phone_book['join_key'] = phone_book['join_key'].astype(str).str.strip()
                    phone_book = phone_book.drop_duplicates(subset=['join_key'], keep='first')
                    
                    merged = pd.merge(loyal_fans, phone_book, on='join_key', how='left')
                    merged[final_phone_col] = merged[final_phone_col].fillna("-")
                    loyal_fans = merged
                else: loyal_fans[final_phone_col] = "-"
            else: loyal_fans[final_phone_col] = "-"

            if final_phone_col in loyal_fans.columns:
                loyal_fans['clean_phone'] = loyal_fans[final_phone_col].apply(clean_phone_number)
            
            valid_fans = loyal_fans[(loyal_fans['clean_phone'] != '-') & (loyal_fans['clean_phone'].str.len() >= 10)].copy()
            if not valid_fans.empty:
                final_df = valid_fans[[buyer_name_col, 'clean_phone', '구매횟수']].copy()
                final_df.columns = ['이름', '전화번호', '비고']

# ------------------------------------------------
# [모드 2] 전체 명부 검색 (Manual Override 추가)
# ------------------------------------------------
else:
    if df_member is None:
        st.info("👈 **왼쪽 사이드바** 2번에 [회원관리(최신전체).xlsx] 파일을 올려주세요.")
    else:
        st.success(f"📂 명부 로드 완료! (총 {len(df_member):,}명)")
        
        # [핵심] 컬럼 수동 선택 기능 추가
        with st.expander("🚨 검색이 안 되나요? (여기를 눌러 컬럼을 확인하세요)", expanded=True):
            st.caption("엑셀 파일의 첫 5줄입니다. '이름'과 '전화번호'가 있는 열을 직접 골라주세요.")
            st.dataframe(df_member.head())
            
            all_cols = df_member.columns.tolist()
            
            # 자동 선택 시도
            auto_n = next((c for c in all_cols if any(x in c for x in ['회원명', '성명', '이름', '조합원명'])), all_cols[0])
            auto_p = next((c for c in all_cols if any(x in c for x in ['휴대전화', '전화', '연락처', '이동전화', 'HP'])), all_cols[-1])
            
            c_sel1, c_sel2 = st.columns(2)
            with c_sel1:
                target_name_col = st.selectbox("👉 '이름' 열 선택", all_cols, index=all_cols.index(auto_n))
            with c_sel2:
                target_phone_col = st.selectbox("👉 '전화번호' 열 선택", all_cols, index=all_cols.index(auto_p))

        # 검색 로직
        c_s1, c_s2 = st.columns([3, 1])
        with c_s1:
            search_keyword = st.text_input("🔍 이름 또는 전화번호 검색", placeholder="예: 김성훈")
        
        # 데이터 준비
        df_search = df_member[[target_name_col, target_phone_col]].copy()
        df_search.columns = ['이름', '전화번호']
        # 공백 제거 (이름에 공백 있는 경우 대비)
        df_search['이름'] = df_search['이름'].astype(str).str.replace(' ', '')
        df_search['전화번호'] = df_search['전화번호'].apply(clean_phone_number)
        
        # 필터링
        if search_keyword:
            clean_keyword = search_keyword.replace(' ', '') # 검색어도 공백 제거
            mask = df_search['이름'].str.contains(clean_keyword) | df_search['전화번호'].str.contains(clean_keyword)
            filtered_result = df_search[mask].copy()
            st.info(f"🔎 '{search_keyword}' 검색 결과: {len(filtered_result)}명")
        else:
            filtered_result = df_search.head(100).copy()
            st.caption("검색어가 없어서 상위 100명만 보여줍니다.")

        if not filtered_result.empty:
            filtered_result['비고'] = "직접검색"
            final_df = filtered_result
            sender_name_default = "품앗이마을"
        else:
            if search_keyword:
                st.warning("검색 결과가 없습니다. (위쪽 '컬럼 설정'에서 열을 제대로 선택했는지 확인해보세요!)")

# ------------------------------------------------
# [공통] 결과 출력
# ------------------------------------------------
st.markdown("---")

if not final_df.empty:
    st.subheader(f"✅ 발송 대상 선택 ({len(final_df)}명)")
    
    final_df.insert(0, "발송", True) 
    
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
    
    selected_df = edited_df[edited_df['발송'] == True].drop(columns=['발송'])
    st.write(f"👉 **최종 선택: {len(selected_df)}명**")

    tab1, tab2 = st.tabs(["📊 엑셀 다운로드", "🚀 문자 발송"])
    
    with tab1:
        if len(selected_df) > 0:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: selected_df.to_excel(writer, index=False)
            st.download_button("📥 선택 명단 엑셀 저장", data=buffer, file_name="선택명단.xlsx")
        else: st.warning("선택된 사람이 없습니다.")

    with tab2:
        st.subheader(f"🚀 메시지 보내기")
        
        if not api_key or not api_secret or not sender_number:
            st.error("👈 왼쪽 사이드바에 API 키와 발신번호를 입력해주세요!")
        elif len(selected_df) == 0:
            st.warning("보낼 사람이 없습니다.")
        else:
            col_msg, col_preview = st.columns([1, 1])
            with col_msg:
                msg_content = st.text_area("💌 메시지 내용", height=150,
                                           placeholder=f"안녕하세요, {sender_name_default}입니다.")
                st.info(f"📤 **발신번호:** {sender_number}")

            with col_preview:
                st.markdown("#### 📱 미리보기")
                st.code(msg_content if msg_content else "(내용을 입력하세요)")
                st.warning(f"💰 예상 비용: {len(selected_df) * 20:,}원")

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
                if st.button(f"🚀 **선택한 {len(selected_df)}명에게 전송**", type="primary"):
                    if not msg_content: st.error("내용을 입력하세요!")
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
