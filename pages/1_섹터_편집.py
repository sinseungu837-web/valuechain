"""
V3 STEP 2 — 섹터 편집 입력 UI.

섹터를 기능 부품 블록으로 해부하고, 종목·공급관계·점유율을
사용자가 직접 정의해 sectors/{name}.json 으로 저장한다.

구조 정보(블록·공급관계·점유율)만 여기서 입력한다.
시세·재무는 yfinance 자동(STEP 3)이라 여기서 안 만진다.
"""
import sys
import os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from data.sector_store import (
    list_sectors, load_sector, save_sector, empty_sector,
)
from data.market_sectors import get_industries, stocks_in_industry


@st.cache_data(ttl=3600)
def _industries():
    return get_industries()


@st.cache_data(ttl=3600)
def _stocks(industry: str):
    return stocks_in_industry(industry)

st.set_page_config(page_title="섹터 편집", page_icon="🛠️", layout="centered")

st.title("🛠️ 섹터 편집")
st.caption("산업을 기능 블록으로 해부하고 종목·공급관계를 정의합니다. "
           "구조 정보만 저장 (시세·재무는 자동 조회).")

WORK_KEY = "v3_working_sector"


# ── 섹터 선택 / 생성 ─────────────────────────────────────────────────────
st.header("1. 섹터 선택 / 생성")
existing = list_sectors()
options = ["➕ 새 섹터 만들기"] + existing
pick = st.selectbox("섹터", options)

col_a, col_b = st.columns(2)
with col_a:
    if pick == "➕ 새 섹터 만들기":
        st.caption("증권 시장 공식 업종에서 선택하거나, 직접 이름을 입력하세요.")
        src = st.radio("이름 정하기", ["시장 업종에서 선택", "직접 입력"],
                       horizontal=True, key="namesrc")
        if src == "시장 업종에서 선택":
            inds = _industries()
            new_name = st.selectbox("시장 업종", inds)
        else:
            new_name = st.text_input("새 섹터 이름", placeholder="예: 로봇")
        if st.button("만들기", use_container_width=True) and (new_name or "").strip():
            st.session_state[WORK_KEY] = empty_sector(new_name.strip())
            st.rerun()
    else:
        if st.button(f"'{pick}' 불러오기", use_container_width=True):
            st.session_state[WORK_KEY] = load_sector(pick)
            st.rerun()
with col_b:
    if WORK_KEY in st.session_state:
        if st.button("작업 닫기", use_container_width=True):
            del st.session_state[WORK_KEY]
            st.rerun()

data = st.session_state.get(WORK_KEY)
if not data:
    st.info("위에서 섹터를 만들거나 불러오면 편집 화면이 나타납니다.")
    st.stop()

st.success(f"편집 중: **{data['sector']}** "
           f"(블록 {len(data['functional_blocks'])} · "
           f"종목 {len(data['companies'])} · "
           f"공급관계 {len(data['supply_relations'])})")
st.divider()


# ── 기능 블록 정의 ───────────────────────────────────────────────────────
st.header("2. 기능 블록 정의")
st.caption("이 산업을 구성하는 기능 부품 블록. 예: 로봇 → 두뇌·시야·관절·전력·골격")
blocks_text = st.text_area(
    "블록 목록 (쉼표로 구분)",
    value=", ".join(data["functional_blocks"]),
    placeholder="두뇌, 시야, 관절, 전력, 골격",
)
if st.button("블록 저장"):
    data["functional_blocks"] = [b.strip() for b in blocks_text.split(",") if b.strip()]
    st.rerun()

blocks = data["functional_blocks"]
st.divider()


# ── 종목 추가 + 기능블록 분류 ────────────────────────────────────────────
st.header("3. 종목 추가 + 기능블록 분류")

# 3-0. 시장 업종에서 구성 종목 자동 불러오기
with st.expander("📥 시장 업종에서 종목 자동 불러오기"):
    st.caption("거래소 업종을 고르면 그 업종 종목을 후보로 보여줍니다. "
               "체크해서 한 번에 추가하세요 (기능블록은 추가 후 개별 지정).")
    inds = _industries()
    # 현재 섹터명이 업종 목록에 있으면 기본 선택
    default_idx = inds.index(data["sector"]) if data["sector"] in inds else 0
    chosen_ind = st.selectbox("업종 선택", inds, index=default_idx, key="bulk_ind")
    cand = _stocks(chosen_ind)
    if not cand:
        st.caption("해당 업종 종목을 불러오지 못했습니다 (서버 문제 또는 빈 업종).")
    else:
        existing_codes = {str(c["code"]) for c in data["companies"]}
        labels, code_map = [], {}
        for s in cand[:60]:
            lab = f"{s['name']} ({s['code']}) {s['market']}"
            labels.append(lab)
            code_map[lab] = s
        picked = st.multiselect(f"{chosen_ind} 종목 ({len(cand)}개 중)", labels)
        if st.button("선택 종목 일괄 추가", use_container_width=True):
            added = 0
            for lab in picked:
                s = code_map[lab]
                if str(s["code"]) in existing_codes:
                    continue
                data["companies"].append({
                    "code": str(s["code"]), "name": s["name"],
                    "functional_blocks": [], "market_share": 0.0,
                    "is_final_product": False,
                })
                added += 1
            st.success(f"{added}개 추가 (기능블록은 아래 목록에서 개별 지정)")
            st.rerun()

if not blocks:
    st.warning("먼저 2번에서 기능 블록을 정의하면 블록 분류가 가능합니다. "
               "지금은 종목만 추가됩니다.")
if True:
    with st.form("add_company", clear_on_submit=True):
        c1, c2 = st.columns(2)
        code = c1.text_input("종목코드", placeholder="277810")
        name = c2.text_input("종목명", placeholder="레인보우로보틱스")
        sel_blocks = st.multiselect("담당 기능 블록", blocks)
        c3, c4 = st.columns(2)
        share = c3.slider("시장점유율 (%)", 0, 100, 0) / 100.0
        is_final = c4.checkbox("완성품 제조사 (금 캐는 사람)")
        if st.form_submit_button("종목 추가", use_container_width=True):
            if code.strip() and name.strip():
                # 중복 코드 제거 후 추가
                data["companies"] = [c for c in data["companies"]
                                     if str(c["code"]) != code.strip()]
                data["companies"].append({
                    "code": code.strip(), "name": name.strip(),
                    "functional_blocks": sel_blocks,
                    "market_share": round(share, 3),
                    "is_final_product": is_final,
                })
                st.rerun()
            else:
                st.error("종목코드와 종목명은 필수입니다.")

# 등록된 종목 목록 (인라인 편집: 블록·점유율·완성품)
if data["companies"]:
    st.markdown("**등록된 종목** (펼쳐서 기능블록·점유율 지정)")
    for i, c in enumerate(data["companies"]):
        tag = "🏁완성품" if c.get("is_final_product") else "🔧부품"
        share_txt = f" · 점유율 {c['market_share']*100:.0f}%" if c.get("market_share") else ""
        head = (f"{tag} {c['name']} ({c['code']}) — "
                f"{'/'.join(c.get('functional_blocks', [])) or '미분류'}{share_txt}")
        with st.expander(head):
            sel = st.multiselect("기능 블록", blocks,
                                 default=[b for b in c.get("functional_blocks", []) if b in blocks],
                                 key=f"eb_{i}")
            e1, e2 = st.columns(2)
            sh = e1.slider("점유율 (%)", 0, 100,
                           int(c.get("market_share", 0) * 100), key=f"es_{i}")
            fin = e2.checkbox("완성품 제조사", value=c.get("is_final_product", False),
                              key=f"ef_{i}")
            b1, b2 = st.columns(2)
            if b1.button("이 종목 적용", key=f"ea_{i}", use_container_width=True):
                c["functional_blocks"] = sel
                c["market_share"] = round(sh / 100.0, 3)
                c["is_final_product"] = fin
                st.rerun()
            if b2.button("삭제", key=f"delc_{i}", use_container_width=True):
                data["companies"].pop(i)
                st.rerun()
st.divider()


# ── 공급관계 입력 ────────────────────────────────────────────────────────
st.header("4. 공급관계 입력 (A → B)")
st.caption("부품사(A)가 완성품/고객사(B)에 납품. 의존도 = B가 A에 거는 의존 정도.")
companies = data["companies"]
if len(companies) < 2:
    st.warning("공급관계를 만들려면 종목이 2개 이상이어야 합니다.")
else:
    name_by_code = {str(c["code"]): c["name"] for c in companies}
    code_list = list(name_by_code.keys())

    with st.form("add_relation", clear_on_submit=True):
        r1, r2 = st.columns(2)
        frm = r1.selectbox("공급사 (A)", code_list,
                           format_func=lambda x: f"{name_by_code[x]} ({x})")
        to = r2.selectbox("고객사 (B)", code_list,
                          format_func=lambda x: f"{name_by_code[x]} ({x})")
        r3, r4 = st.columns(2)
        block = r3.selectbox("관련 블록", blocks if blocks else ["-"])
        part = r4.text_input("부품/품목", placeholder="감속기")
        dep = st.slider("의존도", 0.0, 1.0, 0.3, 0.05)
        if st.form_submit_button("공급관계 추가", use_container_width=True):
            if frm == to:
                st.error("공급사와 고객사가 같을 수 없습니다.")
            else:
                data["supply_relations"].append({
                    "from": frm, "to": to, "block": block,
                    "part": part.strip(), "dependency": round(dep, 3),
                })
                st.rerun()

# 등록된 공급관계
if data["supply_relations"]:
    st.markdown("**등록된 공급관계**")
    name_by_code = {str(c["code"]): c["name"] for c in companies}
    for i, r in enumerate(data["supply_relations"]):
        rc1, rc2 = st.columns([5, 1])
        fn = name_by_code.get(str(r["from"]), r["from"])
        tn = name_by_code.get(str(r["to"]), r["to"])
        rc1.write(f"**{fn}** → **{tn}**  "
                  f"[{r.get('block','')}/{r.get('part','')}] "
                  f"의존도 {r.get('dependency',0):.2f}")
        if rc2.button("삭제", key=f"delr_{i}"):
            data["supply_relations"].pop(i)
            st.rerun()
st.divider()


# ── 저장 ─────────────────────────────────────────────────────────────────
st.header("5. 저장")
st.caption("변경사항은 '저장'을 눌러야 JSON 파일에 기록됩니다.")
if st.button("💾 섹터 저장", type="primary", use_container_width=True):
    path = save_sector(data)
    st.success(f"저장 완료: {os.path.basename(path)}")

with st.expander("현재 JSON 미리보기"):
    st.json(data)
