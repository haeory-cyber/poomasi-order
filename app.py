import streamlit as st
import pandas as pd
import io
import os

# ==========================================
# 1. [기본 설정] 후니님의 철학 반영
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
    st.info("💡 **사용법**\n생산자(농부)와 품앗이님(소비자)을 잇는 도구입니다.")
    
    # 디버깅용: 파일 목록 표시
    st.caption("📂 저장소 파일 목록")
    st.code(os.listdir('.'))

# ==========================================
# 2. [핵심] 절대 실패하지 않는 스마트 로더
# ==========================================
@st.cache_data
def load_smart_data_v3(keyword, type='sales'):
    # 1. 파일 찾기 (이름에 키워드가 포함된 파일 자동 탐색)
    files = os.listdir('.')
    candidates = [f for f in files if keyword in f]
    
    if not candidates:
        return None, f"'{keyword}' 관련 파일을 찾을 수 없습니다."
    
    real_filename = candidates[0] # 가장 먼저 발견된 파일 사용

    # 2. 읽기 시도 (CSV 우선 -> 엑셀 순서)
    # 후니님의 파일은 이름은 xlsx지만 실제론 csv인 경우가 많으므로 csv부터 시도합니다.
    df = None
    encodings = ['utf-8', 'cp949', 'euc-kr']
    
    # 전략 A: 텍스트(CSV)로 읽기
    for enc in encodings:
        try:
            # 엔진을 python으로 설정하여 더 유연하게 읽기
            # on_bad_lines='skip': 칸 수 안 맞는 줄은 무시
            temp_df = pd.read_csv(real_filename, encoding=enc, on_bad_lines='skip', engine='python')
            
            # 헤더 찾기 (키워드 기반)
            keywords = ['농가', '생산자', '상품', '품목'] if type == 'sales' else ['회원', '성명', '전화']
            
            target_row = -1
            # 앞부분 50줄 검사
            for idx in range(min(50, len(temp_df))):
                # 해당 줄의 모든 값을 문자열로 합쳐서 키워드 검사
                row_str = temp_df.iloc[idx].astype(str).str.cat(sep=' ')
                if sum(k in row_str for k in keywords) >= 2:
                    target_row = idx
                    break
            
            if target_row != -1:
                # 헤더를 찾았으면 다시 제대로 읽기
                df = pd.read_csv(real_filename, encoding=enc, header=target_row+1, on_bad_lines='skip', engine='python')
                return clean_columns(df), None
            else:
                # 못 찾았으면 그냥 씀
                return clean_columns(temp_df), None
                
        except Exception:
            continue

    # 전략 B: 엑셀(Excel)로 읽기 (진짜 엑셀일 경우)
    try:
        df = pd.read_excel(real_filename, engine='openpyxl')
        return find_header_and_clean_excel(df, type), None
    except Exception as e:
        return None, f"읽기 실패 ({e})"

def find_header_and_clean_excel(df, type):
    keywords = ['농가', '생산자', '상품', '품목'] if type == 'sales' else ['회원', '성명', '전화']
    target_row = -1
    for idx in range(min(30, len(df))):
        row_str = df.iloc[idx].astype(str).str.cat(sep=' ')
        if sum(k in row_str for k in keywords) >= 2:
            target_row = idx
            break
    if target_row != -1:
        new_header = df.iloc[target_row]
        df = df[target_row+1:]
        df.columns = new_header
    return clean_columns(df)

def clean_columns(df):
    # 컬럼 이름의 공백/줄바꿈 제거
    df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
    return df

# 데이터 로드 실행
# 파일명 전체가 아니라 '키워드'만 넣어서 찾게 함
df_sales, err_sales = load_smart_data_v3('sales_raw', type='sales')
df_member, err_member = load_smart_data_v3('member', type='member')

# ==========================================
# 3. [메인 화면] 품앗이 정신 구현
# ==========================================
st.title("🤝 생산자와 품앗이님을 잇는 '연결 고리'")
st.markdown("##### *\"장사는 이문을 남기는 것이 아니라, 사람을 남기는 것입니다.\"*")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {err_sales}")
else:
    cols = df_sales.columns.tolist()
    
    # 컬럼 자동 매칭
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '이름'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)
    
    if not farmer_col or not buyer_col:
        st.error("🚨 필수 컬럼(농가명, 회원명)을 찾지 못했습니다.")
        st.write("인식된 컬럼들:", cols)
    else:
        # 1. 판매량 많은 순으로 농가 정렬 (인기 농가 우선)
        farmer_counts = df_sales[farmer_col].value_counts()
        all_farmers = farmer_counts.index.tolist()
        
        st.info(f"🌾 총 **{len(all_farmers)}**곳의 생산자님이 검색되었습니다.")
        
        col_search, col_select = st.columns([1, 2])
        with col_search:
            search_query = st.text_input("🔍 농가 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            with col_select:
                selected_farmer = st.selectbox("목록에서 선택하세요 (판매량 많은 순)", filtered_farmers)
            
            # 분석 시작
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            
            if farmer_df.empty:
                st.warning("데이터 없음")
            else:
                # 품앗이님(단골) 집계
                loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
                loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
                
                # 명부 매칭 (연락처 찾기)
                final_phone_col = '연락처'
                matched_with_member = False
                
                if df_member is not None and not df_member.empty:
                    mem_cols = df_member.columns.tolist()
                    mem_name = next((c for c in mem_cols if any(x in c for x in ['회원', '성명', '이름'])), None)
                    mem_phone = next((c for c in mem_cols if any(x in c for x in ['전화', '핸드폰', '연락처'])), None)
                    
                    if mem_name and mem_phone:
                        # 중복 제거 후 병합
                        phone_book = df_member[[mem_name, mem_phone]].drop_duplicates(subset=[mem_name])
                        loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name, how='left')
                        loyal_fans.rename(columns={mem_phone: final_phone_col}, inplace=True)
                        matched_with_member = True
                
                # 명부에서 못 찾았으면 판매 데이터 내 연락처 사용
                if final_phone_col not in loyal_fans.columns:
                    sales_phone = next((c for c in cols if any(x in c for x in ['전화', '핸드폰', '연락처'])), None)
                    if sales_phone:
                        phones = farmer_df[[buyer_col, sales_phone]].drop_duplicates(subset=[buyer_col], keep='last')
                        loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                        loyal_fans.rename(columns={sales_phone: final_phone_col}, inplace=True)
                    else:
                        loyal_fans[final_phone_col] = "번호없음"

                # 결과 화면
                st.markdown("---")
                st.subheader(f"✅ '{selected_farmer}'님을 사랑하는 품앗이님들 ({len(loyal_fans)}명)")
                
                c1, c2 = st.columns([2, 1])
                with c1:
                    # 화면 표시
                    display_cols = [buyer_col, '구매횟수']
                    if final_phone_col in loyal_fans.columns:
                        display_cols.insert(1, final_phone_col)
                    
                    # 컬럼 이름 변경 (사용자 친화적)
                    display_df = loyal_fans[display_cols].rename(columns={buyer_col: '품앗이님 성함'})
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                with c2:
                    st.success("📂 **참여 유도용 파일 생성**")
                    st.markdown("이 파일을 다운받아 **카카오톡 채널**에 활용하세요.")
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        # 엑셀 시트 이름도 깔끔하게
                        loyal_fans.to_excel(writer, index=False, sheet_name='품앗이님명단')
                    
                    file_name_clean = f"{selected_farmer}_품앗이님명단.xlsx".replace("/", "_")
                    st.download_button("📥 엑셀 다운로드", data=buffer, file_name=file_name_clean)
                    
                    if matched_with_member:
                        st.caption("✅ 조합원 명부와 대조하여 정확한 연락처를 확보했습니다.")
                    else:
                        st.caption("⚠️ 판매 기록상의 연락처를 사용했습니다.")

            # (옵션) 인기 상품
            if item_col:
                with st.expander(f"🔎 {selected_farmer}님의 어떤 상품을 좋아하셨나요?"):
                    top_items = farmer_df[item_col].value_counts().head(5)
                    st.bar_chart(top_items)
        else:
            st.warning("검색 결과가 없습니다.")
