import streamlit as st
import pandas as pd
import io

# ==========================================
# 1. [기본 설정]
# ==========================================
st.set_page_config(page_title="품앗이마을 관계망", page_icon="🤝", layout="wide")

with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("비밀번호", type="password")
    if password != "poomasi2026":
        st.warning("관계자 외 출입금지")
        st.stop()
    st.success("환영합니다, 후니님!")
    st.info("💡 **사용법**\n판매 데이터와 조합원 명부를 결합하여 가장 정확한 연락처를 제공합니다.")

# ==========================================
# 2. [데이터 로드] 스마트 헤더 찾기 함수
# ==========================================
@st.cache_data
def load_smart_data(file_name, type='sales'):
    try:
        # 1. 일단 앞부분 읽기
        temp_df = pd.read_excel(file_name, header=None, nrows=20, engine='openpyxl')
        target_row = -1
        
        # 2. 키워드로 헤더 위치 찾기
        keywords = []
        if type == 'sales':
            keywords = ['농가', '생산자', '상품', '품목']
        elif type == 'member':
            keywords = ['회원', '성명', '전화', '휴대폰', '연락처']
            
        for idx, row in temp_df.iterrows():
            row_str = row.astype(str).str.cat(sep=' ')
            # 키워드 중 2개 이상 포함되면 헤더로 인정
            if sum(k in row_str for k in keywords) >= 2:
                target_row = idx
                break
        
        # 3. 데이터 읽기
        if target_row != -1:
            df = pd.read_excel(file_name, header=target_row, engine='openpyxl')
        else:
            df = pd.read_excel(file_name, engine='openpyxl')
            
        # 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
        return df
        
    except Exception as e:
        return None

# 두 파일을 모두 읽어옵니다
df_sales = load_smart_data('sales_raw.xlsx', type='sales')
df_member = load_smart_data('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")
st.markdown("##### *\"데이터는 차갑지만, 우리가 잇는 관계는 따뜻합니다.\"*")
st.markdown("---")

# 파일 상태 점검
if df_sales is None:
    st.error("🚨 `sales_raw.xlsx` (판매 데이터)가 없습니다.")
elif df_member is None:
    st.warning("⚠️ `member.xlsx` (조합원 명부)가 없습니다.")
    st.info("명부 파일이 없으면 판매 데이터에 있는 연락처만 사용합니다. (정확도가 떨어질 수 있음)")
    df_member = pd.DataFrame() # 빈 껍데기 생성

# 데이터가 준비되면 시작
if df_sales is not None:
    # -----------------------------------------------------
    # 컬럼 매칭 (판매 데이터)
    # -----------------------------------------------------
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    buyer_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    item_col = next((c for c in cols if '상품' in c or '품목' in c or '품명' in c), None)
    
    # -----------------------------------------------------
    # 컬럼 매칭 (조합원 명부)
    # -----------------------------------------------------
    mem_name_col = None
    mem_phone_col = None
    
    if not df_member.empty:
        mem_cols = df_member.columns.tolist()
        mem_name_col = next((c for c in mem_cols if '회원' in c or '성명' in c or '이름' in c), None)
        mem_phone_col = next((c for c in mem_cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)

    if farmer_col and buyer_col:
        # 1. 생산자 검색
        st.subheader("1️⃣ 소식을 전할 생산자를 검색하세요")
        all_farmers = sorted(df_sales[farmer_col].dropna().unique().tolist())
        search_query = st.text_input("🔍 농가 이름 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            selected_farmer = st.selectbox("목록에서 선택", filtered_farmers)
            
            # 2. 단골 추출 (판매 데이터 기준)
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # 3. 전화번호 결합 (VLOOKUP 처럼!)
            # 명부 파일이 있고, 매칭 컬럼이 다 있으면 합치기 시도
            if not df_member.empty and mem_name_col and mem_phone_col:
                # 이름 기준으로 합치기
                # 명부에서 중복된 이름이 있을 수 있으니 첫 번째 사람 정보만 가져오거나 등 처리 필요
                # 여기서는 단순하게 merge
                phone_book = df_member[[mem_name_col, mem_phone_col]].drop_duplicates(subset=[mem_name_col])
                
                loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name_col, how='left')
                
                # 연락처 컬럼 이름 정리
                final_phone_col = mem_phone_col
            else:
                # 명부가 없으면 판매 데이터에 있는 전화번호라도 찾아보기
                sales_phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c), None)
                if sales_phone_col:
                    # 판매내역에서 전화번호 가져오기 (가장 최근 것)
                    phones = farmer_df[[buyer_col, sales_phone_col]].drop_duplicates(subset=[buyer_col], keep='last')
                    loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                    final_phone_col = sales_phone_col
                else:
                    final_phone_col = '연락처없음'
                    loyal_fans[final_phone_col] = '확인불가'

            # 4. 결과 출력
            st.markdown("---")
            st.subheader(f"2️⃣ '{selected_farmer}'님의 단골 품앗이님 ({len(loyal_fans)}명)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                # 화면에는 깔끔하게 보여주기 (이름, 전화번호, 구매횟수)
                display_cols = [buyer_col, '구매횟수']
                if final_phone_col != '연락처없음':
                    display_cols.insert(1, final_phone_col)
                    
                st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
                
            with col2:
                st.success("📂 **카톡/문자 발송 파일 생성**")
                output_name = f"{selected_farmer}_단골명단.xlsx"
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    loyal_fans.to_excel(writer, index=False, sheet_name='단골명단')
                    
                st.download_button(
                    label="📥 엑셀 다운로드",
                    data=buffer,
                    file_name=output_name,
                    mime="application/vnd.ms-excel"
                )
                if not df_member.empty:
                    st.caption("✅ 조합원 명부(`member.xlsx`)의 정확한 연락처를 사용했습니다.")
                else:
                    st.caption("⚠️ 조합원 명부가 없어 판매 기록의 연락처를 사용했습니다.")

            # (옵션) 인기 상품
            if item_col:
                with st.expander("🔎 주로 어떤 상품을 사셨나요?"):
                    st.bar_chart(farmer_df[item_col].value_counts().head(5))
                    
        else:
            st.warning("검색 결과가 없습니다.")
    else:
        st.error("필수 컬럼(농가명, 회원명)을 찾지 못했습니다.")
