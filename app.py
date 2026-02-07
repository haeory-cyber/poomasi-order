import streamlit as st
import pandas as pd
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
    
    # ------------------------------------------------
    # [핵심] 파일 정밀 진단 (여기를 보세요!)
    # ------------------------------------------------
    st.markdown("---")
    st.subheader("📂 파일 정밀 진단")
    
    files = os.listdir('.')
    target_file = 'sales_raw.xlsx'
    
    # 대소문자 무시하고 파일 찾기
    real_filename = next((f for f in files if f.lower() == target_file.lower()), None)
    
    if real_filename:
        # 1. 파일 크기 확인
        file_size = os.path.getsize(real_filename)
        st.write(f"**파일명:** `{real_filename}`")
        st.write(f"**크기:** `{file_size} bytes`")
        
        if file_size == 0:
            st.error("🚨 **파일이 비어있습니다 (0 bytes)!**")
            st.info("깃허브에 파일이 이름만 올라가고 내용은 안 올라간 것 같습니다. 다시 업로드(Upload files) 해주세요.")
        elif file_size < 1000:
            st.warning("⚠️ 파일이 너무 작습니다. (내용 확인 필요)")
        else:
            st.success("✅ 파일 용량은 정상입니다.")
            
    else:
        st.error(f"🚨 `{target_file}` 파일을 찾을 수 없습니다.")
        st.code(files)

# ==========================================
# 2. [데이터 로드] 억지로라도 읽어내기
# ==========================================
@st.cache_data
def load_data_force(filename):
    if not filename: return None, "파일 없음"
    
    # 전략 1: CSV로 읽기 (utf-8) - 가장 유력
    try:
        df = pd.read_csv(filename, encoding='utf-8')
        return df, None
    except:
        pass
        
    # 전략 2: CSV로 읽기 (euc-kr) - 한글 윈도우
    try:
        df = pd.read_csv(filename, encoding='cp949')
        return df, None
    except:
        pass

    # 전략 3: 엑셀로 읽기 (openpyxl)
    try:
        df = pd.read_excel(filename, engine='openpyxl')
        return df, None
    except Exception as e:
        return None, f"읽기 실패: {e}"

# 데이터 로드 시도
df = None
error_msg = ""

if real_filename and os.path.getsize(real_filename) > 0:
    df, error_msg = load_data_force(real_filename)

# ==========================================
# 3. [메인 화면]
# ==========================================
st.title("🤝 생산자와 소비자를 잇는 '연결 고리'")

if df is None:
    st.error("🚨 데이터를 불러오지 못했습니다.")
    if error_msg:
        st.write(f"이유: {error_msg}")
    st.info("👈 왼쪽 사이드바의 **[파일 정밀 진단]** 결과를 확인해주세요.")
    st.warning("팁: 만약 파일 크기가 0이라면, 깃허브에서 `sales_raw.xlsx`를 삭제하고 다시 올려주세요.")

else:
    # 헤더 찾기 (데이터가 읽혔다면)
    st.success("🎉 드디어 파일을 읽었습니다!")
    
    # 컬럼 이름 정리 (헤더가 중간에 있는 경우 처리)
    cols = df.columns.astype(str).tolist()
    # '농가'나 '상품'이 포함된 행을 헤더로 다시 설정
    # (코드가 너무 길어지니 일단 읽힌 것만 보여드리고, 다음 단계로 넘어갑니다)
    st.dataframe(df.head(10))
    st.write("위 표가 보이면 성공입니다! 이제 '검색 기능' 코드를 다시 입혀드리면 됩니다.")
