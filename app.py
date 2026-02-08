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
# [설정] 서버에 저장된 연락처 파일명
# ==========================================
# 이 파일이 깃허브(서버) 같은 폴더에 있어야 합니다.
SERVER_CONTACT_FILE = "농가관리 목록_20260208 (전체).xlsx"

# ==========================================
# [중요] 발주 대상 업체 리스트
# ==========================================
VALID_SUPPLIERS = [
    "(주)가보트레이딩", "(주)열두달", "(주)우리밀", "(주)윈윈농수산", "(주)유기샘",
    "(주)케이푸드", "(주)한누리", "G1상사", "mk코리아", "가가호영어조합법인",
    "고삼농협", "금강향수", "나우푸드", "네니아", "농부생각", "농업회사법인(주)담채원",
    "당암tf", "더테스트키친", "도마령영농조합법인", "두레생협", "또또푸드", "로엘팩토리",
    "맛가마", "산백유통", "새롬식품", "생수콩나물영농조합법인", "슈가랩", "씨글로벌(아라찬)",
    "씨에이치하모니", "언니들공방", "에르코스", "엔젤농장", "우리밀농협", "우신영농조합",
    "유기농산", "유안컴퍼니", "인터뷰베이커리", "자연에찬", "장수이야기", "제로웨이스트존",
    "청양농협조합", "청오건강농업회사법인", "청춘농장", "코레드인터내쇼날", "태경F&B",
    "토종마을", "폴카닷(이은경)", "하대목장", "한산항아리소곡주", "함지박(주)", "행복우리식품영농조합",
    "지족점(벌크)", "지족(Y)", "지족점_공동구매", "지족점과일", "지족점야채", "지족매장", "지족점정육"
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
    if pd.isna(phone) or str(phone).strip() in ['-', '', 'nan']: return ''
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
            # 파일 객체일 경우 seek
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            df_raw = pd.read_csv(file_obj, header=None, encoding='utf-8')
        except: return None, "읽기 실패"

    if type == 'sales':
        keywords = ['농가', '공급자', '생산자', '상품', '품목']
    elif type == 'member':
        keywords = ['회원번호', '이름', '휴대전화', '전화번호', '주소']
    elif type == 'info':
        keywords = ['농가명', '휴대전화', '전화번호', '출하상태']
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
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            return pd.read_excel(file_obj) if (hasattr(file_obj, 'name') and file_obj.name.endswith('xlsx')) else pd.read_csv(file_obj), "헤더 못 찾음(기본로드)"
        except: return df_raw, "헤더 못 찾음"

def to_clean_number(x):
    try:
        if pd.isna(x) or str(x).strip() == '': return 0
        clean_str = re.sub(r'[^0-9.-]', '', str(x))
        if clean_str == '' or clean_str == '.': return 0
        return float(clean_str)
    except:
        return 0

def detect_columns(df_columns):
    s_item = next((c for c in df_columns if any(x in c for x in ['상품', '품목'])), None)
    s_qty = next((c for c in df_columns if any(x in c for x in ['판매수량', '총수량'])), None)
    if not s_qty:
        s_qty = next((c for c in df_columns if any(x in c for x in ['수량', '개수'])), None)

    exclude_keywords = ['할인', '반품', '취소', '면세', '과세', '부가세']
    candidates_1 = [c for c in df_columns if ('총' in c and ('판매' in c or '매출' in c))]
    candidates_2 = [c for c in df_columns if (('판매' in c or '매출' in c) and ('액' in c or '금액' in c))]
    candidates_3 = [c for c in df_columns if '금액' in c]

    def is_clean(col_name):
        return not any(bad in col_name for bad in exclude_keywords)

    s_amt = None
    for cand in candidates_1 + candidates_2 + candidates_3:
        if is_clean(cand):
            s_amt = cand
            break
    
    s_farmer = next((c for c in df_columns if any(x in c for x in ['공급자', '농가', '생산자', '거래처'])), None)
    return s_item, s_qty, s_amt, s_farmer

# ==========================================
# 1. [기본 설정 및 사이드바]
# ==========================================
st.set_page_config(page_title="시다비서 (시비)", page_icon="🤖", layout="wide")

if 'sent_history' not in st.session_state:
    st.session_state.sent_history = set()

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
    
    if menu == "📦 자동 채움 발주":
        st.subheader("⚙️ 발주 & 문자 설정")
        api_key = st.text_input("API Key (문자용)", type="password").strip()
        api_secret = st.text_input("API Secret (문자용)", type="password").strip()
        sender_number = st.text_input("발신번호 (숫자만)").strip()
        sender_number = re.sub(r'[^0-9]', '', sender_number)

    st.caption("Powered by Local Food 2.0")

# ==========================================
# 2. [기능 1] 마케팅 & 문자발송
# ==========================================
if menu == "📢 마케팅 & 문자발송":
    st.title("📢 시다비서: 마케팅 & 문자")
    st.info("👈 왼쪽 메뉴에서 '📦 자동 채움 발주'를 선택하시면 발주 업무를 보실 수 있습니다.")

# ==========================================
# 3. [기능 2] 자동 발주 시스템
# ==========================================
elif menu == "📦 자동 채움 발주":
    st.title("📦 시다비서: 자동 채움 발주 + 안심 문자")
    st.markdown("##### **'채움(Fill)'**: 판매 데이터 $\\rightarrow$ **업체별 자동 분류 & 문자 발송**")
    
    with st.sidebar:
        st.subheader("⚙️ 계산 설정")
        budget = st.number_input("💰 오늘 예산", value=500000, step=10000)
        safety = st.slider("안전 계수 (배수)", 1.0, 1.5, 1.1, step=0.1)
        purchase_rate_pct = st.slider("📊 매입 원가율 (%)", 10, 100, 70, step=5)
        purchase_rate = purchase_rate_pct / 100.0
        
        st.subheader("📂 파일 업로드")
        # 판매내역만 업로드 (연락처는 서버에서 로드)
        up_sales_list = st.file_uploader("판매 실적 파일 (여러 개 가능)", type=['xlsx', 'csv'], key='ord_sales', accept_multiple_files=True)
        
        # [서버 파일 로드 상태 표시]
        if os.path.exists(SERVER_CONTACT_FILE):
            st.success(f"📞 서버 연락처 파일 감지됨\n({SERVER_CONTACT_FILE})")
        else:
            st.error(f"❌ 연락처 파일이 서버에 없습니다.\n'{SERVER_CONTACT_FILE}'을 올려주세요.")

    # 연락처 로드 (서버 파일 우선)
    df_phone_map = pd.DataFrame()
    if os.path.exists(SERVER_CONTACT_FILE):
        try:
            # 서버 파일 읽기
            with open(SERVER_CONTACT_FILE, "rb") as f:
                df_i, _ = load_data_smart(f, 'info')
            
            if df_i is not None:
                i_name = next((c for c in df_i.columns if '농가명' in c), None)
                i_phone = next((c for c in df_i.columns if '휴대전화' in c or '전화' in c), None)
                if i_name and i_phone:
                    df_i['clean_name'] = df_i[i_name].astype(str).str.replace(' ', '')
                    df_i['clean_phone'] = df_i[i_phone].apply(clean_phone_number)
                    df_phone_map = df_i.drop_duplicates(subset=['clean_name'])[['clean_name', 'clean_phone']]
                    # st.toast 로드 성공 메시지는 너무 자주 뜨면 귀찮으니 생략하거나 sidebar에 표시
        except Exception as e:
            st.error(f"서버 연락처 파일 로드 중 오류: {e}")

    # 판매내역 로드 및 병합
    df_s = None
    if up_sales_list:
        df_list = []
        for file_obj in up_sales_list:
            d, _ = load_data_smart(file_obj, 'sales')
            if d is not None:
                df_list.append(d)
        
        if df_list:
            df_s = pd.concat(df_list, ignore_index=True)
            if len(up_sales_list) > 1:
                st.toast(f"📄 파일 {len(up_sales_list)}개 합산 완료!", icon="✅")

    if df_s is not None:
        s_item, s_qty, s_amt, s_farmer = detect_columns(df_s.columns.tolist())
        
        if s_item and s_qty and s_amt:
            if s_farmer:
                valid_set = {v.replace(' ', '') for v in VALID_SUPPLIERS}
                df_s['clean_farmer'] = df_s[s_farmer].astype(str).str.replace(' ', '')
                
                def classify_supplier(name):
                    if "지족" in name: return "지족(사입)"
                    elif name in valid_set: return "일반업체"
                    else: return "제외"

                df_s['구분'] = df_s['clean_farmer'].apply(classify_supplier)
                df_target = df_s[df_s['구분'] != "제외"].copy()
                
                if not df_phone_map.empty:
                    df_target = pd.merge(df_target, df_phone_map, left_on='clean_farmer', right_on='clean_name', how='left')
                    df_target.rename(columns={'clean_phone': '전화번호'}, inplace=True)
                else:
                    df_target['전화번호'] = ''
            else:
                df_target = df_s.copy()
                df_target['구분'] = "일반업체"
                df_target['전화번호'] = ''

            df_target[s_qty] = df_target[s_qty].apply(to_clean_number)
            df_target[s_amt] = df_target[s_amt].apply(to_clean_number)
            
            groupby_cols = [s_farmer, s_item, '구분']
            agg_item = df_target.groupby(groupby_cols)[[s_qty, s_amt]].sum().reset_index()
            
            if not df_phone_map.empty and s_farmer:
                agg_item['clean_farmer'] = agg_item[s_farmer].astype(str).str.replace(' ', '')
                agg_item = pd.merge(agg_item, df_phone_map, left_on='clean_farmer', right_on='clean_name', how='left')
                agg_item.rename(columns={'clean_phone': '전화번호'}, inplace=True)
            else:
                agg_item['전화번호'] = ''
            
            agg_item.rename(columns={s_farmer: '업체명', s_item: '상품명', s_qty: '판매량', s_amt: '총판매액'}, inplace=True)
            agg_item = agg_item[agg_item['판매량'] > 0]
            
            agg_item['평균판매가'] = agg_item['총판매액'] / agg_item['판매량']
            agg_item['추정매입가'] = agg_item['평균판매가'] * purchase_rate
            agg_item['발주량'] = np.ceil(agg_item['판매량'] * safety)
            agg_item['예상매입액'] = agg_item['발주량'] * agg_item['추정매입가']
            
            # =================================================================================
            # [UI] 탭 구성
            # =================================================================================
            tab1, tab2 = st.tabs(["🏢 외부업체 건별 발주", "🏪 지족 사입 건별 발주"])
            
            # 공통 렌더링 함수
            def render_order_tab(target_group_name, tab_key):
                df_tab = agg_item[agg_item['구분'] == target_group_name].copy()
                
                if df_tab.empty:
                    st.info(f"{target_group_name} 대상 품목이 없습니다.")
                    return

                st.markdown(f"### 📝 {target_group_name} 문자 발주")
                
                # 검색창
                search_term = st.text_input(f"🔍 {target_group_name} 검색", key=f"search_{tab_key}")
                all_vendors = sorted(df_tab['업체명'].unique())
                target_vendors = [v for v in all_vendors if search_term in v] if search_term else all_vendors

                st.markdown("---")

                for vendor in target_vendors:
                    is_sent = vendor in st.session_state.sent_history
                    v_data = df_tab[df_tab['업체명'] == vendor]
                    default_phone = str(v_data['전화번호'].iloc[0]) if not pd.isna(v_data['전화번호'].iloc[0]) else ''
                    
                    msg_lines = [f"[{vendor} 발주]"]
                    for _, row in v_data.iterrows():
                        msg_lines.append(f"- {row['상품명']}: {int(row['발주량'])}")
                    msg_lines.append("잘 부탁드립니다!")
                    default_msg = "\n".join(msg_lines)
                    
                    icon = "✅" if is_sent else "📩"
                    label = f"{icon} {vendor} (총 {len(v_data)}품목)"
                    
                    with st.expander(label, expanded=not is_sent):
                        c1, c2 = st.columns([1, 2])
                        
                        with c1:
                            input_phone = st.text_input("전화번호", value=default_phone, key=f"phone_{tab_key}_{vendor}")
                            
                            if is_sent:
                                st.success("발송 완료됨")
                            else:
                                if st.button(f"🚀 {vendor} 전송", key=f"btn_{tab_key}_{vendor}", type="primary"):
                                    if not api_key or not api_secret or not sender_number:
                                        st.error("API Key와 발신번호 필요!")
                                    else:
                                        clean_p = clean_phone_number(input_phone)
                                        final_msg = st.session_state.get(f"msg_{tab_key}_{vendor}", default_msg)
                                        
                                        if len(clean_p) < 10:
                                            st.error("전화번호 확인 필요")
                                        else:
                                            ok, res = send_coolsms_direct(api_key, api_secret, sender_number, clean_p, final_msg)
                                            if ok:
                                                st.session_state.sent_history.add(vendor)
                                                st.rerun()
                                            else:
                                                st.error(f"실패: {res.get('errorMessage')}")

                        with c2:
                            st.text_area("내용 수정", value=default_msg, height=150, key=f"msg_{tab_key}_{vendor}")

                with tab1:
                    render_order_tab("일반업체", "ext")

                with tab2:
                    render_order_tab("지족(사입)", "int")
                    
                st.markdown("---")
                st.markdown("### 📊 전체 요약")
                total_all = (agg_item['발주량'] * agg_item['추정매입가']).sum()
                c1, c2 = st.columns(2)
                c1.metric("총 발주 예상액", f"{total_all:,.0f}원")
                c2.metric("예산 잔액", f"{budget - total_all:,.0f}원")

        else: st.error("컬럼 감지 실패! (디버그 창 확인)")
    else:
        st.info("👈 왼쪽에서 '판매내역' 파일을 업로드해주세요.")
