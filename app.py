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
# [설정] 서버 연락처 파일명
# ==========================================
SERVER_CONTACT_FILE = "농가관리 목록_20260208 (전체).xlsx"

# ==========================================
# [중요] 발주 대상 업체 리스트 (화이트리스트)
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
# 0. [공통 함수]
# ==========================================
def send_coolsms_direct(api_key, api_secret, sender, receiver, text):
    try:
        clean_receiver = re.sub(r'[^0-9]', '', str(receiver))
        clean_sender = re.sub(r'[^0-9]', '', str(sender))
        if not clean_receiver or not clean_sender: return False, {"errorMessage": "번호 오류"}

        date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        salt = str(uuid.uuid4())
        data = date + salt
        signature = hmac.new(api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).hexdigest()
        
        headers = {"Authorization": f"HMAC-SHA256 apiKey={api_key}, date={date}, salt={salt}, signature={signature}", "Content-Type": "application/json"}
        url = "https://api.coolsms.co.kr/messages/v4/send"
        payload = {"message": {"to": clean_receiver, "from": clean_sender, "text": text}}
        
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 200: return True, res.json()
        else: return False, res.json()
    except Exception as e: return False, {"errorMessage": str(e)}

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
            if hasattr(file_obj, 'seek'): file_obj.seek(0)
            df_raw = pd.read_csv(file_obj, header=None, encoding='utf-8')
        except: return None, "읽기 실패"

    target_row_idx = -1
    keywords = ['농가', '공급자', '생산자', '상품', '품목'] if type == 'sales' else ['농가명', '휴대전화', '전화번호']
    
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
        clean_str = re.sub(r'[^0-9.-]', '', str(x))
        return float(clean_str) if clean_str not in ['', '.'] else 0
    except: return 0

def detect_columns(df_columns):
    s_item = next((c for c in df_columns if any(x in c for x in ['상품', '품목'])), None)
    s_qty = next((c for c in df_columns if any(x in c for x in ['수량', '개수'])), None)
    
    exclude = ['할인', '반품', '취소', '면세', '과세', '부가세']
    candidates = [c for c in df_columns if ('총' in c and ('판매' in c or '매출' in c))] + \
                 [c for c in df_columns if (('판매' in c or '매출' in c) and ('액' in c or '금액' in c))] + \
                 [c for c in df_columns if '금액' in c]
    
    s_amt = next((c for c in candidates if not any(bad in c for bad in exclude)), None)
    s_farmer = next((c for c in df_columns if any(x in c for x in ['공급자', '농가', '생산자', '거래처'])), None)
    return s_item, s_qty, s_amt, s_farmer

# ==========================================
# 1. [기본 설정 및 로그인]
# ==========================================
st.set_page_config(page_title="시다비서 (시비)", page_icon="🤖", layout="wide")

if 'sent_history' not in st.session_state: st.session_state.sent_history = set()

# 로그인 (사이드바에 최소화)
with st.sidebar:
    st.header("🔒 로그인")
    password = st.text_input("비밀번호", type="password")
    if password != "poom0118**":
        st.warning("비밀번호를 입력하세요.")
        st.stop()
    st.success("접속 완료")
    st.divider()
    st.caption("Developed for Local Food 2.0")

# ==========================================
# 2. [상단 컨트롤 대시보드]
# ==========================================
st.title("🤖 시다비서 (Sida Works)")

# (1) 업무 선택 (가로형)
menu = st.radio("### 1️⃣ 업무를 선택하세요", ["📦 자동 채움 발주", "📢 마케팅 & 문자"], horizontal=True)

if menu == "📦 자동 채움 발주":
    # (2) 설정 패널 (메인 상단 고정)
    with st.container(border=True):
        col_set1, col_set2, col_set3 = st.columns([2, 1, 1])
        
        with col_set1:
            st.markdown("##### ⚙️ 발주 기준 설정")
            c1, c2, c3 = st.columns(3)
            budget = c1.number_input("💰 예산 (원)", value=500000, step=10000)
            safety = c2.slider("📈 안전 계수 (배)", 1.0, 1.5, 1.1, step=0.1)
            purchase_rate = c3.slider("📊 매입 원가율 (%)", 10, 100, 70, step=5) / 100.0
            
            show_all_data = st.checkbox("🕵️‍♂️ 모든 데이터 보기 (필터 해제)", help="화면이 비어있으면 체크하세요!")

        with col_set2:
            st.markdown("##### 🔑 문자 설정")
            api_key = st.text_input("API Key", type="password").strip()
            api_secret = st.text_input("API Secret", type="password").strip()
            
        with col_set3:
            st.markdown("##### 📱 발신번호")
            sender_number = st.text_input("숫자만 입력").strip()
            sender_number = re.sub(r'[^0-9]', '', sender_number)

    # (3) 파일 업로드 (Expander로 숨김 처리 가능)
    with st.expander("📂 **[2단계] 파일 업로드 (여기를 눌러 판매 데이터를 넣으세요)**", expanded=True):
        up_sales_list = st.file_uploader("판매 실적 파일 (여러 개 드래그 가능)", type=['xlsx', 'csv'], accept_multiple_files=True)
        
        # 서버 파일 확인
        if os.path.exists(SERVER_CONTACT_FILE):
            st.success(f"📞 서버 연락처 파일 로드됨: {SERVER_CONTACT_FILE}")
        else:
            st.error(f"❌ 연락처 파일이 서버에 없습니다: {SERVER_CONTACT_FILE}")

    # ==========================================
    # 3. [메인 데이터 로직]
    # ==========================================
    
    # 연락처 로드
    df_phone_map = pd.DataFrame()
    if os.path.exists(SERVER_CONTACT_FILE):
        try:
            with open(SERVER_CONTACT_FILE, "rb") as f:
                df_i, _ = load_data_smart(f, 'info')
            if df_i is not None:
                i_name = next((c for c in df_i.columns if '농가명' in c), None)
                i_phone = next((c for c in df_i.columns if '휴대전화' in c or '전화' in c), None)
                if i_name and i_phone:
                    df_i['clean_name'] = df_i[i_name].astype(str).str.replace(' ', '')
                    df_i['clean_phone'] = df_i[i_phone].apply(clean_phone_number)
                    df_phone_map = df_i.drop_duplicates(subset=['clean_name'])[['clean_name', 'clean_phone']]
        except: pass

    # 판매내역 병합
    df_s = None
    if up_sales_list:
        df_list = []
        for file_obj in up_sales_list:
            d, _ = load_data_smart(file_obj, 'sales')
            if d is not None: df_list.append(d)
        if df_list: df_s = pd.concat(df_list, ignore_index=True)

    if df_s is not None:
        st.divider() # 구분선
        s_item, s_qty, s_amt, s_farmer = detect_columns(df_s.columns.tolist())
        
        if s_item and s_qty and s_amt:
            # 분류 로직
            if s_farmer:
                valid_set = {v.replace(' ', '') for v in VALID_SUPPLIERS}
                df_s['clean_farmer'] = df_s[s_farmer].astype(str).str.replace(' ', '')
                
                def classify(name):
                    if "지족" in name: return "지족(사입)"
                    elif name in valid_set: return "일반업체"
                    else: return "제외" if not show_all_data else "일반업체(강제)"

                df_s['구분'] = df_s['clean_farmer'].apply(classify)
                df_target = df_s[df_s['구분'] != "제외"].copy()
                
                if not df_phone_map.empty:
                    df_target = pd.merge(df_target, df_phone_map, left_on='clean_farmer', right_on='clean_name', how='left')
                    df_target.rename(columns={'clean_phone': '전화번호'}, inplace=True)
                else: df_target['전화번호'] = ''
            else:
                df_target = df_s.copy()
                df_target['구분'] = "일반업체"
                df_target['전화번호'] = ''

            # 데이터 정리
            df_target[s_qty] = df_target[s_qty].apply(to_clean_number)
            df_target[s_amt] = df_target[s_amt].apply(to_clean_number)
            
            groupby_cols = [s_farmer, s_item, '구분']
            agg_item = df_target.groupby(groupby_cols)[[s_qty, s_amt]].sum().reset_index()
            
            if not df_phone_map.empty and s_farmer:
                agg_item['clean_farmer'] = agg_item[s_farmer].astype(str).str.replace(' ', '')
                agg_item = pd.merge(agg_item, df_phone_map, left_on='clean_farmer', right_on='clean_name', how='left')
                agg_item.rename(columns={'clean_phone': '전화번호'}, inplace=True)
            else: agg_item['전화번호'] = ''
            
            agg_item.rename(columns={s_farmer: '업체명', s_item: '상품명', s_qty: '판매량', s_amt: '총판매액'}, inplace=True)
            agg_item = agg_item[agg_item['판매량'] > 0]
            
            agg_item['평균판매가'] = agg_item['총판매액'] / agg_item['판매량']
            agg_item['추정매입가'] = agg_item['평균판매가'] * purchase_rate
            agg_item['발주량'] = np.ceil(agg_item['판매량'] * safety)
            agg_item['예상매입액'] = agg_item['발주량'] * agg_item['추정매입가']
            
            # --- 탭 구성 ---
            tab1, tab2 = st.tabs(["🏢 외부업체 건별 발주", "🏪 지족 사입 건별 발주"])
            
            def render_order_tab(target_groups, tab_key):
                df_tab = agg_item[agg_item['구분'].isin(target_groups)].copy()
                if df_tab.empty:
                    st.info("데이터 없음")
                    return

                # 요약 통계 (상단 배치)
                total_tab = (df_tab['발주량'] * df_tab['추정매입가']).sum()
                c_t1, c_t2 = st.columns([3, 1])
                c_t1.markdown(f"### 📋 {target_groups[0]} 발주 리스트")
                c_t2.metric("그룹 합계", f"{total_tab:,.0f}원")

                # 검색
                search = st.text_input(f"🔍 업체명 검색", key=f"s_{tab_key}", placeholder="업체명 입력...")
                all_v = sorted(df_tab['업체명'].unique())
                targets = [v for v in all_v if search in v] if search else all_v

                for vendor in targets:
                    is_sent = vendor in st.session_state.sent_history
                    v_data = df_tab[df_tab['업체명'] == vendor]
                    phone = str(v_data['전화번호'].iloc[0]) if not pd.isna(v_data['전화번호'].iloc[0]) else ''
                    
                    msg_lines = [f"[{vendor} 발주]"]
                    for _, r in v_data.iterrows(): msg_lines.append(f"- {r['상품명']}: {int(r['발주량'])}")
                    msg_lines.append("잘 부탁드립니다!")
                    default_msg = "\n".join(msg_lines)
                    
                    icon = "✅" if is_sent else "📩"
                    with st.expander(f"{icon} {vendor} ({len(v_data)}건)", expanded=not is_sent):
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            in_phone = st.text_input("전화번호", value=phone, key=f"p_{tab_key}_{vendor}")
                            if not is_sent:
                                if st.button(f"🚀 전송", key=f"b_{tab_key}_{vendor}", type="primary"):
                                    if not api_key or not sender_number: st.error("상단에 API키/발신번호 입력 필요")
                                    else:
                                        final_msg = st.session_state.get(f"m_{tab_key}_{vendor}", default_msg)
                                        ok, res = send_coolsms_direct(api_key, api_secret, sender_number, clean_phone_number(in_phone), final_msg)
                                        if ok:
                                            st.session_state.sent_history.add(vendor)
                                            st.rerun()
                                        else: st.error(f"실패: {res.get('errorMessage')}")
                            else: st.success("발송 완료")
                        with c2:
                            st.text_area("내용", value=default_msg, height=150, key=f"m_{tab_key}_{vendor}")

            with tab1: render_order_tab(["일반업체", "일반업체(강제)"], "ext")
            with tab2: render_order_tab(["지족(사입)"], "int")
            
            st.divider()
            total_all = (agg_item['발주량'] * agg_item['추정매입가']).sum()
            c1, c2 = st.columns(2)
            c1.metric("💰 총 발주 예상액", f"{total_all:,.0f}원")
            c2.metric("💳 예산 잔액", f"{budget - total_all:,.0f}원", delta_color="normal" if budget >= total_all else "inverse")

        else: st.error("데이터 컬럼을 찾을 수 없습니다.")
    else:
        st.info("👆 위 **'파일 업로드'**를 눌러 판매 데이터를 올려주세요.")

elif menu == "📢 마케팅 & 문자":
    st.warning("🚧 마케팅 기능은 현재 통합 작업 중입니다. (이전 코드 사용 가능)")
