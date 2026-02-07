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
import numpy as np

# ==========================================
# 0. [공통 함수] SMS 발송 & 데이터 처리
# ==========================================
def send_coolsms_direct(api_key, api_secret, sender, receiver, text):
    try:
        clean_receiver = re.sub(r'[^0-9]', '', str(receiver))
        clean_sender = re.sub(r'[^0-9]', '', str(sender))

        if not clean_receiver: return False, {"errorCode": "PhoneError", "errorMessage": "수신번호가 없습니다."}
        if not clean_sender: return False, {"errorCode": "SenderError", "errorMessage": "발신번호가 없습니다."}

        date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        salt = str(uuid.uuid4())
        data = date + salt
        signature = hmac.new(api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()
        
        headers = {
            "Authorization": f"HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}",
            "Content-Type": "application/json"
        }
        url = "https://api.coolsms.co.kr/messages/v4/send"
        payload = {
            "message": {
                "to": clean_receiver,
                "from": clean_sender,
                "text": text
            }
        }
        
        res = requests.post(url, json=payload, headers=headers)
        result = res.json()
        
        if res.status_code == 200: return True, result
        else: return False, result
    except Exception as e: return False, {"errorCode": "SystemError", "errorMessage": str(e)}

def clean_phone_number(phone):
    if pd.isna(phone) or phone == '-' or phone == '': return '-'
    clean_num = re.sub(r'[^0-9]', '', str(phone))
    if clean_num.startswith('10') and len(clean_num) >= 10: clean_num = '0' + clean_num
    return clean_num 

@st.cache_data
def load_data_smart(file_obj, type='sales'):
    if file_obj is None: return None, "파일 없음"
    df_raw = None
    try: df_raw = pd.read_excel(file_obj, header=None, engine='openpyxl')
    except:
        try:
            file_obj.seek(0)
            df_raw = pd.read_csv(file_obj, header=None, encoding='utf-8')
        except: return None, "읽기 실패"

    if type == 'sales':
        keywords = ['농가', '공급자', '생산자', '상품', '품목']
    elif type == 'member':
        keywords = ['회원번호', '이름', '휴대전화', '전화번호', '주소']
    elif type == 'master': 
        keywords = ['상품명', '단가', '적정재고', '가격']
    else:
        keywords = []

    target_row_idx = -1
    for idx, row in df_raw.head(20).iterrows():
        row_str = row.astype(str).str.cat(sep=' ')
        match_cnt = sum(1 for k in keywords if k in row_str)
        if match_cnt >= 2:
            target_row_idx = idx
            break
            
    if target_row_idx != -1:
        df_final = df_raw.iloc[target_row_idx+1:].copy()
        df_final.columns = df_raw.iloc[target_row_idx]
        df_final.columns = df_final.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
        df_final = df_final.loc[:, ~df_final.columns.str.contains('^Unnamed')]
        return df_final, None
    else:
        try:
            file_obj.seek(0)
            return pd.read_excel(file_obj) if file_obj.name.endswith('xlsx') else pd.read_csv(file_obj), "헤더 못 찾음(기본로드)"
        except: return df_raw, "헤더 못 찾음"

# ==========================================
# 1. [기본 설정 및 사이드바]
# ==========================================
st.set_page_config(page_title="시다비서 (시비)", page_icon="🤖", layout="wide")

with st.sidebar:
    st.header("🔒 시다비서(시비) 로그인")
    password = st.text_input("비밀번호", type="password")
    if password != "poom0118**":
        st.warning("비밀번호를 입력하세요.")
        st.stop()
    st.success("환영합니다, 후니님!")
    
    st.markdown("---")
    st.markdown("### 🤖 업무 선택")
    menu = st.radio("", ["📢 마케팅 & 문자발송", "📦 자동 채움 발주"])
    st.markdown("---")
    st.caption("Powered by Local Food 2.0")

# ==========================================
# 2. [기능 1] 마케팅 & 문자발송
# ==========================================
if menu == "📢 마케팅 & 문자발송":
    st.title("📢 시다비서: 마케팅 & 문자")
    st.markdown("##### **'이음(Connect)'**: 생산자와 소비자의 마음을 잇습니다.")
    
    with st.sidebar:
        st.subheader("⚙️ 문자 설정")
        api_key_input = st.text_input("API Key", type="password")
        api_secret_input = st.text_input("API Secret", type="password")
        sender_number_input = st.text_input("발신번호 (숫자만)", placeholder="01012345678")
        
        api_key = api_key_input.strip()
        api_secret = api_secret_input.strip()
        sender_number = re.sub(r'[^0-9]', '', sender_number_input)
        
        st.subheader("📂 파일 업로드")
        uploaded_sales = st.file_uploader("1. 판매내역 (타겟팅용)", type=['xlsx', 'csv'], key='mkt_sales')
        uploaded_member = st.file_uploader("2. 회원명부 (검색용)", type=['xlsx', 'csv'], key='mkt_mem')

    df_sales, _ = load_data_smart(uploaded_sales, 'sales')
    df_member, _ = load_data_smart(uploaded_member, 'member')
    
    tab_mode = st.radio("작업 모드:", ["🛒 판매 데이터로 타겟팅", "🔍 전체 명부 검색"], horizontal=True)
    
    final_df = pd.DataFrame()
    sender_name_default = ""

    if "판매 데이터" in tab_mode:
        if df_sales is None: st.info("👈 왼쪽에서 [판매내역] 파일을 올려주세요.")
        else:
            cols = df_sales.columns.tolist()
            farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
            buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
            item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)
            
            if farmer_col and buyer_col:
                farmers = df_sales[farmer_col].unique().tolist()
                c1, c2 = st.columns(2)
                with c1:
                    sel_farmer = st.selectbox("농가 선택", farmers)
                    sender_name_default = sel_farmer
                
                target_df = df_sales[df_sales[farmer_col] == sel_farmer].copy()
                with c2:
                    if item_col:
                        items = ["전체 상품"] + target_df[item_col].unique().tolist()
                        sel_item = st.selectbox("상품 선택", items)
                        if sel_item != "전체 상품": target_df = target_df[target_df[item_col] == sel_item]

                loyal = target_df.groupby(buyer_col).size().reset_index(name='구매횟수').sort_values('구매횟수', ascending=False)
                
                if df_member is not None:
                    m_cols = df_member.columns
                    m_name = next((c for c in m_cols if any(x in c for x in ['이름', '회원명', '성명'])), None)
                    m_phone = next((c for c in m_cols if any(x in c for x in ['휴대전화', '전화', '연락처'])), None)
                    
                    if m_name and m_phone:
                        loyal['key'] = loyal[buyer_col].astype(str).str.replace(' ', '')
                        df_member['key'] = df_member[m_name].astype(str).str.replace(' ', '')
                        mem_clean = df_member.drop_duplicates(subset=['key'])
                        merged = pd.merge(loyal, mem_clean[['key', m_phone]], on='key', how='left')
                        merged.rename(columns={m_phone: '전화번호'}, inplace=True)
                        final_df = merged[[buyer_col, '전화번호', '구매횟수']].fillna('-')
                        final_df.columns = ['이름', '전화번호', '비고']
                    else:
                        st.warning("명부에서 이름/전화번호 컬럼을 못 찾았습니다.")
                        final_df = loyal
                else:
                    final_df = loyal
                    final_df['전화번호'] = '-'
                    final_df.columns = ['이름', '비고', '전화번호']

    else:
        if df_member is None: st.info("👈 왼쪽에서 [회원명부] 파일을 올려주세요.")
        else:
            m_cols = df_member.columns.tolist()
            m_name = next((c for c in m_cols if any(x in c for x in ['이름', '회원명', '성명'])), None)
            m_phone = next((c for c in m_cols if any(x in c for x in ['휴대전화', '전화', '연락처'])), None)
            
            with st.expander("🛠️ 컬럼 설정 (검색 안 되면 클릭)", expanded=(not m_name)):
                c_s1, c_s2 = st.columns(2)
                m_name = c_s1.selectbox("이름 열", m_cols, index=m_cols.index(m_name) if m_name in m_cols else 0)
                m_phone = c_s2.selectbox("전화번호 열", m_cols, index=m_cols.index(m_phone) if m_phone in m_cols else 0)

            keyword = st.text_input("🔍 이름 또는 전화번호 뒷자리 검색")
            
            if keyword:
                df_search = df_member.copy()
                df_search[m_name] = df_search[m_name].astype(str).str.replace(' ', '')
                df_search[m_phone] = df_search[m_phone].apply(clean_phone_number)
                clean_k = keyword.replace(' ', '')
                mask = df_search[m_name].str.contains(clean_k) | df_search[m_phone].str.contains(clean_k)
                res = df_search[mask].copy()
                
                if not res.empty:
                    final_df = res[[m_name, m_phone]].copy()
                    final_df['비고'] = "직접검색"
                    final_df.columns = ['이름', '전화번호', '비고']
                    sender_name_default = "품앗이마을"
                    st.success(f"🔎 {len(final_df)}명 찾음")
                else: st.warning("검색 결과가 없습니다.")

    if not final_df.empty:
        if '전화번호' in final_df.columns:
            final_df['전화번호'] = final_df['전화번호'].apply(clean_phone_number)
            final_df = final_df[final_df['전화번호'].str.len() >= 10]
        
        st.markdown("---")
        st.subheader("✅ 발송 리스트")
        final_df.insert(0, "선택", True)
        edited = st.data_editor(final_df, hide_index=True, use_container_width=True)
        selected = edited[edited['선택']].drop(columns=['선택'])
        
        tab1, tab2, tab3 = st.tabs(["🚀 문자 보내기", "📥 엑셀 다운로드", "🟡 카카오 업로드용"])
        
        with tab1:
            msg_txt = st.text_area("메시지 내용", height=100, placeholder=f"안녕하세요, {sender_name_default}입니다.")
            c_test, c_send = st.columns([1, 2])
            with c_test:
                test_num = st.text_input("테스트 번호", placeholder="내 번호")
                if st.button("내 폰으로 테스트"):
                    if not api_key: st.error("API 키 필요")
                    else:
                        ok, res = send_coolsms_direct(api_key, api_secret, sender_number, test_num, msg_txt)
                        if ok: st.success("성공!")
                        else: st.error(f"실패: {res}")
            with c_send:
                st.write("")
                st.write("")
                if st.button(f"🚀 {len(selected)}명에게 전체 발송", type="primary"):
                    if not api_key: st.error("API 키를 입력하세요.")
                    else:
                        bar = st.progress(0)
                        ok_cnt = 0
                        for i, row in enumerate(selected.itertuples()):
                            ok, _ = send_coolsms_direct(api_key, api_secret, sender_number, row.전화번호, msg_txt)
                            if ok: ok_cnt += 1
                            bar.progress((i+1)/len(selected))
                        st.success(f"{ok_cnt}건 발송 완료!")

        with tab2:
            buf = io.BytesIO()
            selected.to_excel(buf, index=False)
            st.download_button("엑셀 다운로드", buf, "명단.xlsx")
        with tab3:
            kakao_df = selected[['이름', '전화번호']].copy()
            buf_k = io.BytesIO()
            kakao_df.to_excel(buf_k, index=False)
            st.download_button("🟡 카카오 업로드용 다운로드", buf_k, "카카오발송용.xlsx")

# ==========================================
# 3. [기능 2] 자동 발주 시스템
# ==========================================
elif menu == "📦 자동 채움 발주":
    st.title("📦 시다비서: 자동 채움 발주")
    st.markdown("##### **'채움(Fill)'**: 데이터로 빈 공간을 정확히 채웁니다.")
    
    with st.sidebar:
        st.subheader("⚙️ 발주 설정")
        budget = st.number_input("💰 오늘 예산", value=500000, step=10000)
        safety = st.slider("안전 계수 (배수)", 1.0, 1.5, 1.1, step=0.1)
        st.caption(f"판매량의 **{safety}배**를 발주합니다.")
        
        st.subheader("📂 파일 업로드")
        up_sales = st.file_uploader("1. 어제 판매내역 (포스)", type=['xlsx', 'csv'], key='ord_sales')
        up_master = st.file_uploader("2. 발주 마스터 (단가표)", type=['xlsx', 'csv'], key='ord_master')
        
        df_tpl = pd.DataFrame({'상품명': ['두부', '콩나물'], '단가': [2000, 1500]})
        buf_t = io.BytesIO()
        df_tpl.to_excel(buf_t, index=False)
        st.download_button("📥 단가표 양식 받기", buf_t, "단가표_양식.xlsx")

    if up_sales and up_master:
        df_s, _ = load_data_smart(up_sales, 'sales')
        df_m, _ = load_data_smart(up_master, 'master')
        
        if df_s is not None and df_m is not None:
            s_item = next((c for c in df_s.columns if any(x in c for x in ['상품', '품목'])), None)
            s_qty = next((c for c in df_s.columns if any(x in c for x in ['수량', '개수'])), None)
            m_item = next((c for c in df_m.columns if any(x in c for x in ['상품', '품목'])), None)
            m_price = next((c for c in df_m.columns if any(x in c for x in ['단가', '가격'])), None)
            
            if s_item and m_item and m_price:
                if s_qty:
                    agg = df_s.groupby(s_item)[s_qty].sum().reset_index()
                    agg.columns = ['상품명', '판매량']
                else:
                    agg = df_s[s_item].value_counts().reset_index()
                    agg.columns = ['상품명', '판매량']

                agg['key'] = agg['상품명'].astype(str).str.replace(' ', '')
                df_m['key'] = df_m[m_item].astype(str).str.replace(' ', '')
                
                merged = pd.merge(agg, df_m[['key', m_price]], on='key', how='left')
                merged.rename(columns={m_price: '단가'}, inplace=True)
                merged['단가'] = merged['단가'].fillna(0)
                
                merged['발주량'] = np.ceil(merged['판매량'] * safety)
                merged['금액'] = merged['발주량'] * merged['단가']
                
                st.subheader("🚀 발주 제안서")
                st.caption(f"안전계수 {safety}배 적용 완료")
                
                edited = st.data_editor(
                    merged[['상품명', '판매량', '발주량', '금액', '단가']],
                    column_config={
                        "발주량": st.column_config.NumberColumn(min_value=0, step=1),
                        "금액": st.column_config.NumberColumn(format="%d원", disabled=True),
                        "단가": st.column_config.NumberColumn(format="%d원", disabled=True)
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                edited['최종금액'] = edited['발주량'] * edited['단가']
                total = edited['최종금액'].sum()
                
                st.markdown("---")
                c_m1, c_m2 = st.columns(2)
                c_m1.metric("총 발주금액", f"{total:,.0f}원")
                if total > budget:
                    c_m2.metric("예산 초과", f"{total - budget:,.0f}원", delta_color="inverse")
                    st.error("🚨 예산 초과!")
                else:
                    c_m2.metric("잔액", f"{budget - total:,.0f}원")
                    st.success("✅ 예산 통과")
                
                final_order = edited[edited['발주량'] > 0].copy()
                buf_f = io.BytesIO()
                final_order.to_excel(buf_f, index=False)
                st.download_button("📥 최종 발주서 엑셀 다운로드", buf_f, "자동발주서.xlsx", type="primary")

                txt = f"[발주] 총 {len(final_order)}건 / {total:,.0f}원\n"
                for _, r in final_order.iterrows():
                    txt += f"- {r['상품명']}: {int(r['발주량'])}개\n"
                st.text_area("카톡 전송용", txt)

            else: st.error("파일에 [상품명, 단가, 수량] 컬럼이 꼭 있어야 합니다.")
    else:
        st.info("👈 왼쪽에서 파일들을 업로드해주세요.")
