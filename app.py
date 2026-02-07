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
import requests # 기본 통신 도구

# ==========================================
# 0. [내장함수] 쿨에스엠에스 직접 연결 (설치X)
# ==========================================
def send_coolsms_direct(api_key, api_secret, sender, receiver, text):
    """
    라이브러리 없이 직접 쿨에스엠에스(솔라피) API를 호출하는 함수
    """
    # 1. 서명 생성 (보안)
    date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    salt = str(uuid.uuid4())
    data = date + salt
    signature = hmac.new(api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {
        "Authorization": f"HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}",
        "Content-Type": "application/json"
    }
    
    # 2. 메시지 준비
    url = "https://api.coolsms.co.kr/messages/v4/send"
    payload = {
        "message": {
            "to": receiver,
            "from": sender,
            "text": text
        }
    }
    
    # 3. 발송 (requests 사용)
    try:
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200:
            return True, res.json()
        else:
            return False, res.json()
    except Exception as e:
        return False, str(e)

# ==========================================
# 1. [기본 설정 & 디자인]
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
    st.caption("발급받은 키를 넣어주세요.")
    
    api_key = st.text_input("API Key", type="password", placeholder="NCS...")
    api_secret = st.text_input("API Secret", type="password", placeholder="CCPY...")
    sender_number = st.text_input("발신번호 (하이픈 없이)", placeholder="01012345678")
    
    st.markdown("---")
    st.header("📂 데이터 업로드")
    uploaded_sales = st.file_uploader("1️⃣ 판매 내역 (포스 파일)", type=['xlsx', 'csv'])
    uploaded_member = st.file_uploader("2️⃣ 조합원 명부 (선택사항)", type=['xlsx', 'csv'])
    
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

def clean_phone_number(phone):
    if pd.isna(phone) or phone == '-' or phone == '': return '-'
    clean_num = re.sub(r'[^0-9]', '', str(phone))
    if clean_num.startswith('10') and len(clean_num) >= 10: clean_num = '0' + clean_num
    return clean_num 

# ==========================================
# 3. [메인 로직]
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")

if uploaded_sales:
    df_sales, msg_sales = load_data_from_upload(uploaded_sales, 'sales')
else:
    df_sales, msg_sales = None, "파일 없음"

if uploaded_member:
    df_member, msg_member = load_data_from_upload(uploaded_member, 'member')
elif local_member:
    with open(local_member, 'rb') as f:
        file_content = io.BytesIO(f.read())
        df_member, msg_member = load_data_from_upload(file_content, 'member')
else:
    df_member, msg_member = None, "명부 없음"

if df_sales is None:
    st.info("👈 **왼쪽 사이드바**에서 판매 내역 파일을 업로드해주세요.")
else:
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_name_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    buyer_id_col = next((c for c in cols if any(x in c for x in ['회원번호', '조합원번호', '번호'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)

    if not farmer_col or not buyer_name_col:
        st.error("🚨 필수 컬럼 누락")
    else:
        # --- 대상 추출 ---
        all_farmers = df_sales[farmer_col].value_counts().index.tolist()
        
        c1, c2 = st.columns([1, 1])
        with c1:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
            filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
            selected_farmer = st.selectbox("농가 선택", filtered_farmers)
            
        farmer_df_full = df_sales[df_sales[farmer_col] == selected_farmer].copy()
        
        with c2:
            if item_col:
                all_items = farmer_df_full[item_col].value_counts().index.tolist()
                item_options = ["전체 상품 보기"] + all_items
                selected_item = st.selectbox("📦 품목 선택", item_options)
            else:
                selected_item = "전체 상품 보기"

        if selected_item != "전체 상품 보기":
            target_df = farmer_df_full[farmer_df_full[item_col] == selected_item].copy()
        else:
            target_df = farmer_df_full

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

        # 전화번호 정제
        if final_phone_col in loyal_fans.columns:
            loyal_fans['clean_phone'] = loyal_fans[final_phone_col].apply(clean_phone_number)

        valid_fans = loyal_fans[(loyal_fans['clean_phone'] != '-') & (loyal_fans['clean_phone'].str.len() >= 10)].copy()
        
        if not valid_fans.empty:
            final_df = valid_fans.groupby([buyer_name_col, 'clean_phone'])['구매횟수'].sum().reset_index()
            final_df = final_df.sort_values(by='구매횟수', ascending=False)
        else:
            final_df = pd.DataFrame(columns=[buyer_name_col, 'clean_phone', '구매횟수'])

        # ==========================================
        # 4. [탭 구성] 조회 vs 발송
        # ==========================================
        st.markdown("---")
        tab1, tab2 = st.tabs(["📊 명단 조회 & 엑셀 다운", "🚀 **[NEW] 자동 문자 발송**"])
        
        with tab1:
            st.subheader(f"✅ 발송 대상: 총 {len(final_df)}명")
            if len(final_df) > 0:
                c_d1, c_d2, c_d3 = st.columns(3)
                with c_d1:
                    buffer1 = io.BytesIO()
                    with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer: final_df.to_excel(writer, index=False)
                    st.download_button("📥 분석용 엑셀 (상세)", data=buffer1, file_name=f"{selected_farmer}_상세.xlsx")
                with c_d2:
                    k_df = final_df[[buyer_name_col, final_phone_col]].copy()
                    k_df.columns = ['이름', '전화번호']
                    buf2 = io.BytesIO()
                    with pd.ExcelWriter(buf2, engine='xlsxwriter') as w: k_df.to_excel(w, index=False)
                    st.download_button("🟡 카카오 업로드용", data=buf2, file_name=f"{selected_farmer}_카카오.xlsx")
                with c_d3:
                    s_df = final_df[[buyer_name_col, final_phone_col]].copy()
                    s_df.columns = ['이름', '휴대폰번호']
                    buf3 = io.BytesIO()
                    with pd.ExcelWriter(buf3, engine='xlsxwriter') as w: s_df.to_excel(w, index=False)
                    st.download_button("🟢 행복ICT 업로드용", data=buf3, file_name=f"{selected_farmer}_문자.xlsx")
                    
                st.dataframe(final_df, use_container_width=True)
            else:
                st.warning("매칭된 연락처가 없습니다.")

        with tab2:
            st.subheader(f"🚀 '{selected_farmer}'님 소식 보내기")
            
            if not api_key or not api_secret or not sender_number:
                st.error("👈 왼쪽 사이드바에 'API Key', 'Secret', '발신번호'를 입력해주세요!")
            elif len(final_df) == 0:
                st.warning("발송할 대상이 없습니다.")
            else:
                col_msg, col_preview = st.columns([1, 1])
                
                with col_msg:
                    msg_content = st.text_area("💌 메시지 내용 (90바이트 초과 시 장문 자동 전환)", height=200,
                                               placeholder=f"안녕하세요, {selected_farmer}입니다.\n오늘 신선한 {selected_item}가 입고되었습니다!")
                    st.info(f"📤 **발신번호:** {sender_number}")
                    st.caption("주의: 실제 발송되며 비용이 발생합니다.")

                with col_preview:
                    st.markdown("#### 📱 미리보기")
                    st.code(msg_content if msg_content else "(내용을 입력하세요)")
                    st.warning(f"💰 예상 비용: 약 **{len(final_df) * 20:,}원**")

                st.markdown("---")
                
                send_col1, send_col2 = st.columns([1, 3])
                with send_col1:
                    test_phone = st.text_input("테스트 발송 번호", placeholder="01012345678")
                    if st.button("내 폰으로 테스트"):
                        if not test_phone: st.error("번호를 입력하세요.")
                        else:
                            success, res = send_coolsms_direct(api_key, api_secret, sender_number, test_phone, msg_content)
                            if success: st.success(f"✅ 전송 성공! ({res.get('groupInfo', {}).get('log', 'OK')})")
                            else: st.error(f"❌ 전송 실패: {res}")

                with send_col2:
                    st.write("") 
                    st.write("") 
                    if st.button(f"🚀 **진짜로 {len(final_df)}명에게 전체 발송**", type="primary"):
                        if not msg_content:
                            st.error("메시지 내용을 입력하세요!")
                        else:
                            progress_bar = st.progress(0)
                            targets = final_df['clean_phone'].tolist()
                            success_cnt = 0
                            
                            for i, phone in enumerate(targets):
                                # 0.5초 딜레이 (안전장치)
                                time.sleep(0.5)
                                suc, _ = send_coolsms_direct(api_key, api_secret, sender_number, phone, msg_content)
                                if suc: success_cnt += 1
                                progress_bar.progress((i + 1) / len(targets))
                            
                            st.success(f"🎉 **발송 완료!** (총 {len(targets)}건 중 {success_cnt}건 성공)")
                            st.balloons()
