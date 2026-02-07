import streamlit as st
import pandas as pd

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
    st.info("💡 **사용법**\n생산자별로 단골 품앗이님을 찾아주는 도구입니다.")

# ==========================================
# 2. [데이터 로드] 스마트 헤더 찾기 (핵심!)
# ==========================================
@st.cache_data
def load_data():
    file_name = 'sales_raw.xlsx'
    try:
        # 1단계: 일단 앞부분 20줄만 가져와서 '진짜 제목줄'이 어디인지 찾습니다.
        # (제목이나 결재란 때문에 첫 줄이 헤더가 아닐 수 있음)
        temp_df = pd.read_excel(file_name, header=None, nrows=20, engine='openpyxl')
        
        target_row = -1
        for idx, row in temp_df.iterrows():
            # 한 줄을 글자로 합쳐서 검사 ('농가'와 '상품'이라는 단어가 동시에 있는 줄 찾기)
            row_str = row.astype(str).str.cat(sep=' ')
            if ('농가' in row_str or '생산자' in row_str) and ('상품' in row_str or '품목' in row_str):
                target_row = idx
                break
        
        # 2단계: 찾은 위치부터 다시 제대로 읽습니다.
        if target_row != -1:
            df = pd.read_excel(file_name, header=target_row, engine='openpyxl')
            # 컬럼명 공백 제거 (오류 방지)
            df.columns = df.columns.astype(str).str.replace(' ', '').str.replace('\n', '')
            return df
        else:
            # 못 찾았으면 그냥 첫 줄부터 읽어봅니다 (혹시 모르니)
            return pd.read_excel(file_name, engine='openpyxl')
            
    except Exception as e:
        st.error(f"데이터를 읽는 중 오류가 발생했습니다: {e}")
        return None

df = load_data()

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")
st.markdown("##### *\"행복한신선농장의 딸기가 입고되었습니다! 누구에게 알려드려야 할까요?\"*")
st.markdown("---")

if df is None:
    st.error("🚨 `sales_raw.xlsx` 파일을 찾지 못했거나 열 수 없습니다.")
else:
    # 컬럼 찾기 (유연하게)
    cols = df.columns.tolist()
    farmer_col = next((c for c in cols if '농가' in c or '공급자' in c or '생산자' in c), None)
    # '회원' 또는 '조합원' 또는 '구매자'
    member_col = next((c for c in cols if '회원' in c or '구매자' in c or '성명' in c), None)
    item_col = next((c for c in cols if '상품' in c or '품목' in c or '품명' in c), None)
    phone_col = next((c for c in cols if '전화' in c or '핸드폰' in c or '연락처' in c), None)

    if farmer_col and member_col:
        # 1. 생산자 선택
        farmers = sorted(df[farmer_col].dropna().unique().tolist())
        st.subheader("1️⃣ 소식을 전할 생산자를 선택하세요")
        selected_farmer = st.selectbox("농가 목록", farmers)
        
        # 2. 분석
        farmer_df = df[df[farmer_col] == selected_farmer].copy()
        
        # 3. 단골 집계
        group_cols = [member_col]
        if phone_col: group_cols.append(phone_col)
        
        loyal_fans = farmer_df.groupby(group_cols).size().reset_index(name='구매횟수')
        loyal_fans = loyal_fans.sort_values(by='구매횟수', ascending=False)
        
        # 4. 결과 출력
        st.subheader(f"2️⃣ '{selected_farmer}'님을 기다리는 품앗이님들 ({len(loyal_fans)}명)")
        st.write("구매 횟수가 많은 순서대로 보여줍니다.")
        
        st.dataframe(loyal_fans, use_container_width=True, hide_index=True)
        
        # 5. 인기 상품 보기
        if item_col:
            with st.expander(f"🔎 {selected_farmer}님의 인기 상품 보기"):
                top_items = farmer_df[item_col].value_counts().head(5)
                st.bar_chart(top_items)
    else:
        st.error("엑셀 파일에서 필요한 컬럼(농가명, 회원명)을 찾지 못했습니다.")
        st.write("컴퓨터가 인식한 컬럼 이름들:", cols)
        st.info("팁: 엑셀 파일의 첫 줄에 제목이 너무 길게 들어있지 않은지 확인해주세요.")
