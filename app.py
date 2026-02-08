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
# [중요] 발주 대상 업체 리스트 (최신 업데이트)
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
    # '지족' 관련은 로직에서 자동 분류
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
    if pd.isna(phone) or phone == '-' or phone == '': return '' # 전화번호 없으면 빈값
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
    elif type == 'info': # 농가 정보 파일
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
            file_obj.seek(0)
            return pd.read_excel(file_obj) if file_obj.name.endswith('xlsx') else pd.read_csv(file_obj), "헤더 못 찾음(기본로드)"
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
        # 문자 발송 정보 입력
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
    # (마케팅 코드는 이전과 동일, 생략 없이 유지하려면 이전 코드 붙여넣기 필요)
    # 여기서는 발주 기능 집중을 위해 placeholder 처리하거나 이전 마케팅 코드를 그대로 둡니다.
    # [사용자 편의를 위해 마케팅 코드는 간략히 안내만 띄웁니다. 필요시 이전 코드 사용]
    st.write("---")
    st.write("현재 이 페이지는 **[발주 기능 업데이트]**에 집중되어 있습니다.")
    st.write("마케팅 기능을 사용하시려면 이전 코드를 사용하시거나, 요청해주시면 통합해드립니다.")

# ==========================================
# 3. [기능 2] 자동 발주 시스템
# ==========================================
elif menu == "📦 자동 채움 발주":
    st.title("📦 시다비서: 자동 채움 발주 + 문자 발송")
    st.markdown("##### **'채움(Fill)'**: 판매 데이터 분석 $\\rightarrow$ 업체별 자동 문자 발주")
    
    with st.sidebar:
        st.subheader("⚙️ 계산 설정")
        budget = st.number_input("💰 오늘 예산", value=500000, step=10000)
        safety = st.slider("안전 계수 (배수)", 1.0, 1.5, 1.1, step=0.1)
        purchase_rate_pct = st.slider("📊 매입 원가율 (%)", 10, 100, 70, step=5)
        purchase_rate = purchase_rate_pct / 100.0
        
        st.subheader("📂 파일 업로드")
        up_sales = st.file_uploader("1. 어제 판매내역 (포스)", type=['xlsx', 'csv'], key='ord_sales')
        up_info = st.file_uploader("2. 업체 연락처 (농가관리 목록)", type=['xlsx', 'csv'], key='ord_info')

    if up_sales:
        df_s, _ = load_data_smart(up_sales, 'sales')
        
        # 연락처 정보 로드
        df_phone_map = pd.DataFrame()
        if up_info:
            df_i, _ = load_data_smart(up_info, 'info')
            if df_i is not None:
                # 필요한 컬럼 찾기
                i_name = next((c for c in df_i.columns if '농가명' in c), None)
                i_phone = next((c for c in df_i.columns if '휴대전화' in c or '전화' in c), None)
                
                if i_name and i_phone:
                    df_i['clean_name'] = df_i[i_name].astype(str).str.replace(' ', '')
                    df_i['clean_phone'] = df_i[i_phone].apply(clean_phone_number)
                    # 중복 제거 (같은 이름이면 첫 번째 번호 사용)
                    df_phone_map = df_i.drop_duplicates(subset=['clean_name'])[['clean_name', 'clean_phone']]
                    st.toast(f"📞 업체 연락처 {len(df_phone_map)}건 로드 완료!", icon="✅")
        
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
                    
                    # 연락처 매핑 (Merge)
                    if not df_phone_map.empty:
                        df_target = pd.merge(df_target, df_phone_map, left_on='clean_farmer', right_on='clean_name', how='left')
                        df_target.rename(columns={'clean_phone': '전화번호'}, inplace=True)
                    else:
                        df_target['전화번호'] = ''
                        
                else:
                    df_target = df_s.copy()
                    df_target['구분'] = "일반업체"
                    df_target['전화번호'] = ''

                # 데이터 세탁 & 집계
                df_target[s_qty] = df_target[s_qty].apply(to_clean_number)
                df_target[s_amt] = df_target[s_amt].apply(to_clean_number)
                
                # 그룹핑 (전화번호 포함)
                groupby_cols = [s_farmer, s_item, '구분', '전화번호'] if s_farmer else [s_item, '구분']
                # 전화번호가 있으면 그걸 유지해야 하므로 groupby에 포함. (전화번호가 여러개면 갈라질 수 있음 -> max로 통일)
                
                # 1차 집계: 상품별
                agg_item = df_target.groupby([s_farmer, s_item, '구분'])[[s_qty, s_amt]].sum().reset_index()
                # 전화번호 붙이기 (업체명 기준)
                if not df_phone_map.empty:
                    agg_item['clean_farmer'] = agg_item[s_farmer].astype(str).str.replace(' ', '')
                    agg_item = pd.merge(agg_item, df_phone_map, left_on='clean_farmer', right_on='clean_name', how='left')
                    agg_item.rename(columns={'clean_phone': '전화번호'}, inplace=True)
                else:
                    agg_item['전화번호'] = ''
                
                agg_item.rename(columns={s_farmer: '업체명'}, inplace=True)
                agg_item = agg_item[agg_item['판매량'] > 0]
                
                # 계산
                agg_item['평균판매가'] = agg_item['총판매액'] / agg_item['판매량']
                agg_item['추정매입가'] = agg_item['평균판매가'] * purchase_rate
                agg_item['발주량'] = np.ceil(agg_item['판매량'] * safety)
                agg_item['예상매입액'] = agg_item['발주량'] * agg_item['추정매입가']
                
                # ----------------------------------------------------
                # [UI] 탭 분리
                # ----------------------------------------------------
                tab1, tab2 = st.tabs(["🏢 외부업체 발주 (문자발송)", "🏪 지족 사입 & 요약"])
                
                # --- Tab 1: 외부 업체 (문자 발송 핵심) ---
                with tab1:
                    st.markdown("### 🏢 외부 협력업체 발주서")
                    df_ext = agg_item[agg_item['구분'] == '일반업체'].copy()
                    
                    if df_ext.empty:
                        st.info("발주 대상 외부 업체가 없습니다.")
                    else:
                        # 1. 상세 수량 수정 에디터
                        st.markdown("#### 1️⃣ 수량 확인 및 수정")
                        edited_ext = st.data_editor(
                            df_ext[['업체명', '상품명', '판매량', '발주량', '예상매입액', '전화번호']],
                            column_config={
                                "업체명": st.column_config.TextColumn(disabled=True),
                                "상품명": st.column_config.TextColumn(disabled=True),
                                "발주량": st.column_config.NumberColumn(min_value=0, step=1),
                                "전화번호": st.column_config.TextColumn(disabled=True, help="아래에서 수정 가능"),
                                "예상매입액": st.column_config.NumberColumn(format="%d원", disabled=True),
                            },
                            use_container_width=True, hide_index=True, height=400
                        )
                        
                        # 2. 발주서 문자 생성 및 번호 수정
                        st.markdown("---")
                        st.markdown("#### 2️⃣ 발주 문자 보내기 (번호 수정 가능)")
                        
                        # 업체별로 데이터 묶기
                        final_order_list = edited_ext[edited_ext['발주량'] > 0]
                        
                        if final_order_list.empty:
                            st.warning("발주할 수량이 없습니다.")
                        else:
                            # 업체별 메시지 생성
                            sms_prep_list = []
                            for vendor, group in final_order_list.groupby('업체명'):
                                phone_num = group['전화번호'].iloc[0] # 첫번째 값 가져옴
                                if pd.isna(phone_num): phone_num = ''
                                
                                # 메시지 만들기
                                msg_lines = [f"[{vendor} 발주]"]
                                total_items = 0
                                for _, row in group.iterrows():
                                    msg_lines.append(f"- {row['상품명']}: {int(row['발주량'])}")
                                    total_items += 1
                                msg_lines.append(f"총 {total_items}종. 잘 부탁드립니다!")
                                full_msg = "\n".join(msg_lines)
                                
                                sms_prep_list.append({
                                    "업체명": vendor,
                                    "전화번호": phone_num,
                                    "발송내용": full_msg,
                                    "전송": False # 체크박스 기본값
                                })
                            
                            df_sms_prep = pd.DataFrame(sms_prep_list)
                            
                            # 여기서 전화번호 수정 가능하게!
                            edited_sms_list = st.data_editor(
                                df_sms_prep,
                                column_config={
                                    "업체명": st.column_config.TextColumn(disabled=True),
                                    "전화번호": st.column_config.TextColumn(required=True, help="직접 입력/수정 가능"),
                                    "발송내용": st.column_config.TextColumn(width="large"),
                                    "전송": st.column_config.CheckboxColumn(label="보낼 곳 선택", default=True)
                                },
                                use_container_width=True, hide_index=True
                            )
                            
                            # 전송 버튼
                            col_btn, col_info = st.columns([1, 3])
                            with col_btn:
                                if st.button("🚀 선택한 업체에 문자 발송", type="primary"):
                                    if not api_key or not api_secret or not sender_number:
                                        st.error("왼쪽 사이드바에 API Key와 발신번호를 입력해주세요!")
                                    else:
                                        targets = edited_sms_list[edited_sms_list['전송'] == True]
                                        if targets.empty:
                                            st.warning("선택된 업체가 없습니다.")
                                        else:
                                            success_count = 0
                                            progress_bar = st.progress(0)
                                            status_area = st.empty()
                                            
                                            for i, row in enumerate(targets.itertuples()):
                                                p_num = clean_phone_number(row.전화번호)
                                                if len(p_num) < 10:
                                                    st.toast(f"❌ {row.업체명}: 전화번호 오류 ({row.전화번호})")
                                                    continue
                                                    
                                                ok, res = send_coolsms_direct(api_key, api_secret, sender_number, p_num, row.발송내용)
                                                if ok:
                                                    success_count += 1
                                                else:
                                                    st.toast(f"❌ {row.업체명} 실패: {res.get('errorMessage')}")
                                                
                                                progress_bar.progress((i + 1) / len(targets))
                                            
                                            st.success(f"총 {len(targets)}건 중 {success_count}건 발송 성공!")

                # --- Tab 2: 지족 사입 & 요약 ---
                with tab2:
                    st.markdown("### 🏪 지족점 사입 (내부용)")
                    df_int = agg_item[agg_item['구분'] == '지족(사입)'].copy()
                    
                    if not df_int.empty:
                        st.data_editor(df_int[['상품명', '판매량', '발주량', '예상매입액']], hide_index=True)
                        total_int = (df_int['발주량'] * df_int['추정매입가']).sum()
                        st.info(f"사입 예산 합계: {total_int:,.0f}원")
                    else:
                        st.info("내부 사입 품목 없음")
                        
                    st.markdown("---")
                    st.markdown("### 📊 전체 요약")
                    total_all = (agg_item['발주량'] * agg_item['추정매입가']).sum()
                    
                    c1, c2 = st.columns(2)
                    c1.metric("총 발주 예상액", f"{total_all:,.0f}원")
                    c2.metric("예산 잔액", f"{budget - total_all:,.0f}원", delta_color="normal" if budget >= total_all else "inverse")

            else: st.error("컬럼 감지 실패! (디버그 창 확인)")
    else:
        st.info("👈 왼쪽에서 '어제 판매내역' 파일을 업로드해주세요.")
