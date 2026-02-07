import streamlit as st
import pandas as pd
import os
import io

# ==========================================
# 1. [기본 설정]
# ==========================================
st.set_page_config(page_title="품앗이마을 관계망", page_icon="🤝", layout="wide")

with st.sidebar:
    st.header("🔒 품앗이님 확인")
    password = st.text_input("비밀번호", type="password")
    if password != "poom0118**":
        st.warning("관계자 외 출입금지")
        st.stop()
    st.success("환영합니다, 후니님!")
    
    # [진단] 현재 폴더의 파일 목록 보여주기
    st.markdown("---")
    st.caption("📂 현재 저장소 파일 목록")
    files = os.listdir('.')
    st.code(files)

# ==========================================
# 2. [데이터 로드] 스마트 파일 찾기 & 읽기
# ==========================================
@st.cache_data
def load_smart_data(target_name, type='sales'):
    # 1. 파일 이름 융통성 있게 찾기 (대소문자 무시)
    current_files = os.listdir('.')
    real_filename = next((f for f in current_files if f.lower() == target_name.lower()), None)
    
    if real_filename is None:
        return None, f"파일을 찾을 수 없습니다. (찾는 이름: {target_name})"
    
    try:
        # 2. 헤더 찾기 로직
        temp_df = pd.read_excel(real_filename, header=None, nrows=20, engine='openpyxl')
        target_row = -1
        
        keywords = []
        if type == 'sales':
            keywords = ['농가', '생산자', '상품', '품목', '공급자']
        elif type == 'member':
            keywords = ['회원', '성명', '전화', '휴대폰', '연락처', '조합원']
            
        for idx, row in temp_df.iterrows():
            row_str = row.astype(str).str.cat(sep=' ')
            if sum(k in row_str for k in keywords) >= 2:
                target_row = idx
                break
        
        # 3. 데이터 읽기
        if target_row != -1:
            df = pd.read_excel(real_filename, header=target_row, engine='openpyxl')
        else:
            df = pd.read_excel(real_filename, engine='openpyxl')
            
        # 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
        return df, None
        
    except Exception as e:
        return None, str(e)

# 데이터 로드 시도
df_sales, err_sales = load_smart_data('sales_raw.xlsx', type='sales')
df_member, err_member = load_smart_data('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")
st.markdown("##### *\"데이터는 차갑지만, 우리가 잇는 관계는 따뜻합니다.\"*")
st.markdown("---")

# 에러 메시지 상세 출력 (진실의 방)
if df_sales is None:
    st.error(f"🚨 판매 데이터(`sales_raw.xlsx`) 로드 실패!")
    st.error(f"에러 상세 내용: {err_sales}")
    st.info("👈 왼쪽 사이드바의 '파일 목록'에 sales_raw 파일이 있는지 확인해주세요.")
    
elif df_member is None:
    st.warning("⚠️ 조합원 명부(`member.xlsx`)를 찾을 수 없거나 읽지 못했습니다.")
    if err_member:
        st.caption(f"이유: {err_member}")
    st.info("명부가 없어도 판매 데이터의 연락처로 작동합니다.")
    df_member = pd.DataFrame()

# 정상 작동 시 화면
if df_sales is not None:
    # 컬럼 매칭
    cols = df_sales.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    buyer_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    item_col = next((c for c in cols if '상품' in c or '품목' in c or '품명' in c), None)
    
    # 명부 컬럼 매칭
    mem_name_col = None
    mem_phone_col = None
    if not df_member.empty:
        mem_cols = df_member.columns.tolist()
        mem_name_col = next((c for c in mem_cols if '회원' in c or '성명' in c or '이름' in c), None)
        mem_phone_col = next((c for c in mem_cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)

    if farmer_col and buyer_col:
        st.subheader("1️⃣ 소식을 전할 생산자를 검색하세요")
        all_farmers = sorted(df_sales[farmer_col].dropna().unique().tolist())
        search_query = st.text_input("🔍 농가 이름 검색", placeholder="예: 행복")
        
        filtered_farmers = [f for f in all_farmers if search_query in str(f)] if search_query else all_farmers
        
        if filtered_farmers:
            selected_farmer = st.selectbox("목록에서 선택", filtered_farmers)
            
            # 분석 및 결합
            farmer_df = df_sales[df_sales[farmer_col] == selected_farmer].copy()
            loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
            loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
            
            # 연락처 결합 로직
            if not df_member.empty and mem_name_col and mem_phone_col:
                # 명부에서 중복 제거 후 병합
                phone_book = df_member[[mem_name_col, mem_phone_col]].drop_duplicates(subset=[mem_name_col])
                loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name_col, how='left')
                final_phone_col = mem_phone_col
            else:
                sales_phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c), None)
                if sales_phone_col:
                    phones = farmer_df[[buyer_col, sales_phone_col]].drop_duplicates(subset=[buyer_col], keep='last')
                    loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                    final_phone_col = sales_phone_col
                else:
                    final_phone_col = '연락처없음'
                    loyal_fans[final_phone_col] = '확인불가'

            # 결과 출력
            st.markdown("---")
            st.subheader(f"2️⃣ '{selected_farmer}'님의 단골 품앗이님 ({len(loyal_fans)}명)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
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
                st.download_button("📥 엑셀 다운로드", data=buffer, file_name=output_name, mime="application/vnd.ms-excel")
                
            if item_col:
                with st.expander("🔎 인기 상품 보기"):
                    st.bar_chart(farmer_df[item_col].value_counts().head(5))
        else:
            st.warning("검색 결과가 없습니다.")
    else:
        st.error(f"엑셀 파일 형식을 인식하지 못했습니다. (확인된 컬럼: {cols})")
