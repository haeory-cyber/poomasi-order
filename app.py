import streamlit as st
import pandas as pd
import io
import os

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
    st.caption("📂 저장소 파일 현황")
    st.code(os.listdir('.'))

# ==========================================
# 2. [데이터 로드] 만능 로더
# ==========================================
@st.cache_data
def load_smart_data(target_name, type='sales'):
    files = os.listdir('.')
    real_filename = next((f for f in files if f.lower() == target_name.lower()), None)
    
    if not real_filename: return None, "파일 없음"

    df = None
    try:
        df = pd.read_excel(real_filename, engine='openpyxl')
    except:
        try:
            df = pd.read_csv(real_filename, encoding='utf-8')
        except:
            try:
                df = pd.read_csv(real_filename, encoding='cp949')
            except Exception as e:
                return None, f"읽기 실패: {e}"
    
    if df is not None:
        keywords = []
        if type == 'sales':
            keywords = ['농가', '생산자', '상품', '품목', '공급자']
        elif type == 'member':
            keywords = ['회원', '성명', '전화', '휴대폰', '연락처', '조합원', '이름']
            
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
            
        df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
        return df, None
        
    return None, "알 수 없는 오류"

df_sales, err_sales = load_smart_data('sales_raw.xlsx', type='sales')
df_member, err_member = load_smart_data('member.xlsx', type='member')

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")

if df_sales is None:
    st.error(f"🚨 판매 데이터 로드 실패: {err_sales}")
else:
    cols = df_sales.columns.tolist()
    
    farmer_col = next((c for c in cols if any(x in c for x in ['농가', '공급자', '생산자'])), None)
    buyer_col = next((c for c in cols if any(x in c for x in ['회원', '구매자', '성명', '주문자', '소비자', '이름'])), None)
    item_col = next((c for c in cols if any(x in c for x in ['상품', '품목', '품명'])), None)
    
    st.info(f"📊 **데이터 분석 상태** (농가 컬럼: `{farmer_col}` / 구매자 컬럼: `{buyer_col}`)")

    if not farmer_col or not buyer_col:
        st.error("🚨 필수 컬럼(농가명, 구매자명)을 찾지 못했습니다.")
    else:
        # ---------------------------------------------------------
        # [수정] 농가 목록을 '판매량 순'으로 정렬 (인기순)
        # ---------------------------------------------------------
        # 1. 판매 건수 계산
        farmer_counts = df_sales[farmer_col].value_counts()
        # 2. 많은 순서대로 이름 리스트 만들기
        all_farmers = farmer_counts.index.tolist()
        
        st.write(f"🌾 현재 총 **{len(all_farmers)}**곳의 농가(생산자)가 검색되었습니다.")
        
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
                loyal_fans = farmer_df.groupby(buyer_col).size().reset_index(name='구매횟수')
                loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
                
                # 명부 매칭
                final_phone_col = '연락처'
                if df_member is not None and not df_member.empty:
                    mem_cols = df_member.columns.tolist()
                    mem_name = next((c for c in mem_cols if any(x in c for x in ['회원', '성명', '이름'])), None)
                    mem_phone = next((c for c in mem_cols if any(x in c for x in ['전화', '핸드폰', '연락처'])), None)
                    
                    if mem_name and mem_phone:
                        phone_book = df_member[[mem_name, mem_phone]].drop_duplicates(subset=[mem_name])
                        loyal_fans = pd.merge(loyal_fans, phone_book, left_on=buyer_col, right_on=mem_name, how='left')
                        loyal_fans.rename(columns={mem_phone: final_phone_col}, inplace=True)
                
                if final_phone_col not in loyal_fans.columns:
                    sales_phone = next((c for c in cols if any(x in c for x in ['전화', '핸드폰', '연락처'])), None)
                    if sales_phone:
                        phones = farmer_df[[buyer_col, sales_phone]].drop_duplicates(subset=[buyer_col], keep='last')
                        loyal_fans = pd.merge(loyal_fans, phones, on=buyer_col, how='left')
                        loyal_fans.rename(columns={sales_phone: final_phone_col}, inplace=True)
                    else:
                        loyal_fans[final_phone_col] = "번호없음"

                st.markdown("---")
                st.subheader(f"✅ '{selected_farmer}'님의 단골 ({len(loyal_fans)}명)")
                
                c1, c2 = st.columns([2, 1])
                with c1:
                    display_cols = [buyer_col, '구매횟수']
                    if final_phone_col in loyal_fans.columns:
                        display_cols.insert(1, final_phone_col)
                    st.dataframe(loyal_fans[display_cols], use_container_width=True, hide_index=True)
                with c2:
                    st.success("📂 **카톡 발송용 파일**")
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        loyal_fans.to_excel(writer, index=False)
                    st.download_button("📥 엑셀 다운로드", data=buffer, file_name=f"{selected_farmer}_단골.xlsx")
        else:
            st.warning("검색 결과가 없습니다.")
