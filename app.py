
# ENVY v26.2 • Single-file with HuggingFace AI mode (Key Embedded) ⚠️ Local Use Only
import streamlit as st
import random, html, requests

st.set_page_config(page_title="ENVY v26.2 (HF Key Embedded)", page_icon="🔑", layout="wide")

HF_API_KEY = "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"  # ⚠️ Hardcoded key (unsafe for sharing)

# -------------------- utils --------------------
def copy_button(text: str, key: str):
    safe_text = html.escape(text).replace("\n","\\n").replace("'","\\'")
    html_str = f"""
    <div style='display:flex;gap:8px;align-items:center;margin:6px 0;'>
      <input id='inp_{key}' value='{html.escape(text)}' style='flex:1;padding:6px 8px;' />
      <button onclick="navigator.clipboard.writeText('{safe_text}')">복사</button>
    </div>
    """
    st.components.v1.html(html_str, height=46)

# -------------------- name generator --------------------
def render_namegen():
    st.subheader("상품명 생성기 (규칙/AI 모드)")
    brand = st.text_input("브랜드", "envy")
    base = st.text_input("베이스 키워드", "K-coffee mix")
    keywords = st.text_input("연관키워드", "Maxim, Kanu, Korea")
    badwords = st.text_input("금칙어", "copy, fake, replica")
    limit = st.slider("글자수 제한", 20, 120, 80)
    mode = st.radio("모드 선택", ["규칙 기반","HuggingFace 무료"], horizontal=True)

    def filter_and_trim(cands:list) -> list:
        bans = {w.strip().lower() for w in badwords.split(",") if w.strip()}
        out=[]
        for t in cands:
            t2 = " ".join(t.split())
            if any(b in t2.lower() for b in bans): continue
            if len(t2)>limit: t2=t2[:limit]
            out.append(t2)
        return out

    if st.button("생성"):
        kws=[k.strip() for k in keywords.split(",") if k.strip()]
        cands=[]
        if mode=="규칙 기반":
            for _ in range(5):
                pref=random.choice(["[New]","[Hot]","[Korea]"])
                suf=random.choice(["2025","FastShip","HotDeal"])
                join=random.choice([" | "," · "," - "])
                cands.append(f"{pref} {brand}{join}{base} {', '.join(kws[:2])} {suf}")
        elif mode=="HuggingFace 무료":
            if not HF_API_KEY:
                st.warning("HuggingFace Key 없음 → 규칙 기반으로 대체")
                for _ in range(5):
                    cands.append(f"{brand} {base} {random.choice(kws)}")
            else:
                st.info("HuggingFace Inference API 호출 (무료 플랜 제한 있음)")
                API_URL = "https://api-inference.huggingface.co/models/distilgpt2"
                headers = {"Authorization": f"Bearer {HF_API_KEY}" }
                payload = {"inputs": f"상품명 추천: {brand} {base} {', '.join(kws)}"}
                try:
                    resp = requests.post(API_URL, headers=headers, json=payload, timeout=10)
                    if resp.status_code==200:
                        data = resp.json()
                        text = data[0].get("generated_text","")
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        cands = lines[:5] if lines else [text[:limit]]
                    else:
                        st.error(f"HuggingFace API 오류: {resp.status_code}")
                except Exception as e:
                    st.error(f"HuggingFace 호출 실패: {e}")
        cands = filter_and_trim(cands)
        st.session_state["name_cands"]=cands

    st.markdown("---")
    st.write("생성 결과")
    for idx, t in enumerate(st.session_state.get("name_cands", [])):
        st.write(f"{idx+1}. {t}")
        copy_button(t, key=f"cand_{idx}")

# -------------------- main --------------------
st.title("🔑 ENVY v26.2 • HuggingFace Key Embedded (Local Only)")
st.caption("규칙 기반 + HuggingFace AI 모드 (Key 하드코딩 버전, 공유 금지)")

tab1, = st.tabs(["상품명 생성기"])
with tab1: render_namegen()
