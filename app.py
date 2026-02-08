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
# [중요] 발주 대상 업체 리스트 (업데이트됨)
# ==========================================
VALID_SUPPLIERS = [
    "(영)옥천친환경농업인연합사업단", "(주)가보트레이딩", "(주)건강생활연구소", "(주)기운찬", "(주)열두달",
    "(주)우리밀", "(주)윈윈농수산", "(주)유기샘", "(주)참옻들", "(주)케이푸드", "(주)한누리",
    "2대째바느질(박희선)", "G1상사", "mk코리아", "가가호영어조합법인", "강경대동젓갈상회", "고삼농협",
    "공주농산물가공영농조합법인", "금강향수", "나우푸드", "네니아", "논산줌협동조합", "농부생각",
    "농업회사법인 금산흑삼 주식회사", "농업회사법인 신탄진주조(주)", "농업회사법인 주식회사 연스토리",
    "농업회사법인(주)담채원", "농업회사법인(주)미녀와김치", "농업회사법인(주)자모", "농업회사법인내포(주)",
    "농업회사법인천지애", "당암tf", "대전부르스주조 농업회사법인(유)", "대청호민물고기직판장", "더테스트키친",
    "도마령영농조합법인", "도영미(미마지)", "두레생협", "또또푸드", "로엘팩토리", "맛가마",
    "백석올미영농조합", "베큘리 주식회사", "보령수협", "사자산영농조합법인", "산계뜰", "산백유통",
    "산수정미소", "산애들애농원 농업회사법인 주식회사", "새롬식품", "생수콩나물영농조합법인", "서산명가",
    "서천군수협", "성신양봉(희당꿀,지업사)", "세종로얄양봉원", "수림원 농업회사법인 주식회사", "슈가랩",
    "씨글로벌(아라찬)", "씨에이치하모니", "언니들공방", "에너지전환해유사회적협동조합", "에르코스", "엔젤농장",
    "열린부뚜막", "옥천누리영농조합법인", "우리밀농협", "우신영농조합", "원정정미소(박준상)", "원주생명농업",
    "유기농산", "유안컴퍼니", "인터뷰베이커리", "잇다", "잇초", "자연에찬", "장수군장애인보호작업장",
    "장수이야기", "제로웨이스트존", "지족점(벌크)", "지족(Y)", "지족점_공동구매", "지족점과일",
    "지족점야채", "지족매장", "지족점정육", "천호산농원식품", "청양농협조합", "청오건강농업회사법인",
    "청춘농장", "코레드인터내쇼날", "태경F&B", "토종마을", "통영수산", "폴카닷(이은경)", "하대목장",
    "한산항아리소곡주", "함지박(주)", "해나루한과영농조합법인", "해피트리목공협동조합", "행복우리식품영농조합",
    "행복한신선농장", "향지촌", "홍성유기농영농조합법인", "흙살림", "관저매장"
]

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
    st.markdown("##### **'채움(Fill)'**: 판매 데이터 기반 자동 발주 (단가표 불필요)")
    
    with st.sidebar:
        st.subheader("⚙️ 발주 설정")
        budget = st.number_input("💰 오늘 예산", value=500000, step=10000)
        safety = st.slider("안전 계수 (배수)", 1.0, 1.5, 1.1, step=0.1)
        
        st.markdown("---")
        purchase_rate_pct = st.slider("📊 매입 원가율 (%)", 10, 100, 70, step=5)
        purchase_rate = purchase_rate_pct / 100.0
        
        st.subheader("📂 파일 업로드")
        up_sales = st.file_uploader("1. 어제 판매내역 (포스)", type=['xlsx', 'csv'], key='ord_sales')

    if up_sales:
        df_s, _ = load_data_smart(up_sales, 'sales')
        
        if df_s is not None:
            # 컬럼 자동 감지
            s_item = next((c for c in df_s.columns if any(x in c for x in ['상품', '품목'])), None)
            s_qty = next((c for c in df_s.columns if any(x in c for x in ['수량', '개수'])), None)
            s_amt = next((c for c in df_s.columns if any(x in c for x in ['금액', '매출', '판매액'])), None)
            s_farmer = next((c for c in df_s.columns if any(x in c for x in ['공급자', '농가', '생산자', '거래처'])), None)
            
            if s_item and s_qty and s_amt:
                # 1. 화이트리스트 필터링
                if s_farmer:
                    valid_set = {v.replace(' ', '') for v in VALID_SUPPLIERS}
                    df_s['clean_farmer'] = df_s[s_farmer].astype(str).str.replace(' ', '')
                    df_target = df_s[df_s['clean_farmer'].isin(valid_set)].copy()
                    
                    st.info(f"🔎 전체 품목 중 매입처(업체) 품목 **{len(df_target)}건**을 식별했습니다.")
                else:
                    st.warning("⚠️ '농가/공급자' 컬럼이 없어 필터링 없이 진행합니다.")
                    df_target = df_s.copy()

                # 2. 데이터 집계 (업체별 + 상품별)
                df_target[s_qty] = pd.to_numeric(df_target[s_qty], errors='coerce').fillna(0)
                df_target[s_amt] = pd.to_numeric(df_target[s_amt], errors='coerce').fillna(0)
                
                groupby_cols = [s_farmer, s_item] if s_farmer else [s_item]
                agg = df_target.groupby(groupby_cols)[[s_qty, s_amt]].sum().reset_index()
                
                if s_farmer:
                    agg.columns = ['업체명', '상품명', '판매량', '총판매액']
                else:
                    agg.columns = ['상품명', '판매량', '총판매액']
                    agg['업체명'] = '미확인'

                agg = agg[agg['판매량'] > 0]

                # 3. 계산
                agg['평균판매가'] = agg['총판매액'] / agg['판매량']
                agg['추정매입가'] = agg['평균판매가'] * purchase_rate
                agg['발주량'] = np.ceil(agg['판매량'] * safety)
                agg['예상매입액'] = agg['발주량'] * agg['추정매입가']
                
                # 4. [NEW] 화면 분할 (요약 vs 상세)
                tab1, tab2 = st.tabs(["📋 품목별 상세 발주 (수정)", "🏢 업체별 요약 (확인)"])
                
                # --- Tab 1: 상세 수정 ---
                with tab1:
                    st.markdown("### 🔍 발주 리스트 (업체별 정렬됨)")
                    
                    # 필터 기능
                    all_suppliers = sorted(agg['업체명'].unique().tolist())
                    sel_suppliers = st.multiselect("업체만 골라보기 (비워두면 전체)", all_suppliers)
                    
                    if sel_suppliers:
                        view_df = agg[agg['업체명'].isin(sel_suppliers)].copy()
                    else:
                        view_df = agg.copy()
                    
                    # 정렬: 업체명 가나다 -> 판매액 높은순
                    view_df = view_df.sort_values(by=['업체명', '총판매액'], ascending=[True, False])
                    
                    edited = st.data_editor(
                        view_df[['업체명', '상품명', '판매량', '발주량', '예상매입액', '추정매입가']],
                        column_config={
                            "업체명": st.column_config.TextColumn("업체명", disabled=True),
                            "상품명": st.column_config.TextColumn("상품명", disabled=True),
                            "발주량": st.column_config.NumberColumn("📦 발주량", min_value=0, step=1),
                            "예상매입액": st.column_config.NumberColumn(format="%d원", disabled=True),
                            "추정매입가": st.column_config.NumberColumn(format="%d원", disabled=True),
                        },
                        use_container_width=True,
                        hide_index=True,
                        height=500
                    )
                    
                    # 합계 및 다운로드
                    current_total = (edited['발주량'] * edited['추정매입가']).sum()
                    st.markdown(f"#### 💰 총 발주금액: :blue[{current_total:,.0f}원]")
                    
                    if current_total > budget:
                        st.error(f"🚨 예산 {budget:,.0f}원 초과!")
                    else:
                        st.success(f"✅ 예산 잔액: {budget - current_total:,.0f}원")
                    
                    # 엑셀 다운로드 (전체)
                    final_order = edited[edited['발주량'] > 0].copy()
                    buf_f = io.BytesIO()
                    final_order.to_excel(buf_f, index=False)
                    
                    if sel_suppliers:
                        st.warning("⚠️ 필터가 적용된 상태입니다. 다운로드 파일에는 **화면에 보이는 항목만** 포함됩니다.")
                    
                    st.download_button("📥 발주서 엑셀 다운로드", buf_f, "발주서_최종.xlsx", type="primary")

                # --- Tab 2: 업체별 요약 ---
                with tab2:
                    st.markdown("### 🏢 업체별 매입 예상액")
                    # 원본 agg 기준 요약 (수정된 발주량 반영 안 됨 주의 - 안내 필요)
                    summary = agg.groupby('업체명')['예상매입액'].sum().reset_index()
                    summary = summary.sort_values('예상매입액', ascending=False)
                    
                    st.dataframe(
                        summary,
                        column_config={
                            "예상매입액": st.column_config.ProgressColumn(
                                "매입 규모",
                                format="%d원",
                                min_value=0,
                                max_value=summary['예상매입액'].max()
                            )
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                    st.info("💡 이 요약표는 초기 계산값 기준입니다. (상세 탭에서 수량을 수정해도 여기엔 바로 반영되지 않습니다.)")

            else: st.error("파일 컬럼 오류: [상품명, 수량, 금액]이 필요합니다.")
    else:
        st.info("👈 왼쪽에서 '어제 판매내역' 파일을 업로드해주세요.")
