import streamlit as st
import os
import requests
import pandas as pd # New: For managing history
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# 1. INITIAL SETUP
load_dotenv()
INITIAL_G_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
INITIAL_IK_TOKEN = os.getenv("INDIAN_KANOON_TOKEN", "").strip()
HISTORY_FILE = "case_history.csv"

st.set_page_config(page_title="Legal Master Workstation", layout="wide")

# 2. SESSION STATE
if "google_key" not in st.session_state: st.session_state.google_key = INITIAL_G_KEY
if "ik_token" not in st.session_state: st.session_state.ik_token = INITIAL_IK_TOKEN
if "ik_balance" not in st.session_state: st.session_state.ik_balance = 500.00
if "g_draft" not in st.session_state: st.session_state.g_draft = ""
if "s_draft" not in st.session_state: st.session_state.s_draft = ""
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = []

# --- NEW: HISTORY FUNCTIONS ---
def save_to_history(case_type, facts, draft):
    new_data = pd.DataFrame([{
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Type": case_type,
        "Facts": facts[:50] + "...",
        "Full_Draft": draft
    }])
    if not os.path.isfile(HISTORY_FILE):
        new_data.to_csv(HISTORY_FILE, index=False)
    else:
        new_data.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

def get_history():
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame()

# 3. MOCK DATA
def get_mock_data():
    return [
        {"title": "M.C. Mehta v. Union of India", "court": "Supreme Court", "headline": "Environmental protection and absolute liability."},
        {"title": "Vishaka v. State of Rajasthan", "court": "Supreme Court", "headline": "Guidelines for workplace safety."}
    ]

# 4. TABS INTERFACE
tab_work, tab_settings = st.tabs(["⚖️ Workstation", "⚙️ Settings"])

with tab_settings:
    st.header("🔑 API Configuration")
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.google_key = st.text_input("Gemini API Key", value=st.session_state.google_key, type="password")
    with col_b:
        st.session_state.ik_token = st.text_input("Indian Kanoon Token", value=st.session_state.ik_token, type="password")
    if st.button("💾 Save & Refresh"):
        st.rerun()

with tab_work:
    with st.sidebar:
        st.title("👨‍⚖️ Admin")
        doc_type = st.selectbox("Document Type", ["Writ Petition", "Legal Notice", "Bail Application", "Contract"])
        jurisdiction = st.selectbox("Jurisdiction", ["Supreme Court", "High Court", "District Court"])
        
        st.divider()
        st.subheader("📜 Case History")
        history_df = get_history()
        if not history_df.empty:
            for i, row in history_df.tail(5).iterrows(): # Show last 5
                if st.button(f"📅 {row['Date']} - {row['Type']}", key=f"hist_{i}"):
                    st.session_state.final_master = row['Full_Draft']
        else:
            st.caption("No history found.")

    # --- MAIN WORK AREA ---
    st.title(f"⚖️ {doc_type} Draft")
    facts = st.text_area("Case Facts:", placeholder="Enter client story...", height=150)

    btn_col1, btn_col2, _ = st.columns([1, 1, 3])
    
    with btn_col1:
        if st.button("🔍 Search Cases", use_container_width=True):
            if len(st.session_state.ik_token) < 5:
                st.session_state.search_results = get_mock_data()
            else:
                # Real API Logic
                headers = {'Authorization': f'Token {st.session_state.ik_token}'}
                res = requests.post(f"https://api.indiankanoon.org/search/?formInput={facts}", headers=headers)
                if res.status_code == 200:
                    st.session_state.search_results = res.json().get('docs', [])
                    st.session_state.ik_balance -= 0.50
            st.rerun()

    with btn_col2:
        if st.button("🚀 Draft Document", type="primary", use_container_width=True):
            if not st.session_state.google_key:
                st.error("Add Gemini Key in Settings!")
            else:
                client = genai.Client(api_key=st.session_state.google_key)
                with st.spinner("Analyzing..."):
                    res_g = client.models.generate_content(model='gemini-2.0-flash', contents=f"Draft {doc_type} for {jurisdiction}. Facts: {facts}")
                    st.session_state.g_draft = res_g.text
                    res_s = client.models.generate_content(model='gemini-2.0-flash', contents=f"Risks for: {facts}")
                    st.session_state.s_draft = res_s.text
            st.rerun()

    # --- RESULTS ---
    if st.session_state.search_results:
        with st.expander("📚 Relevant Precedents", expanded=True):
            for doc in st.session_state.search_results[:2]:
                st.markdown(f"**{doc.get('title')}**")
                st.caption(doc.get('headline'))

    if st.session_state.g_draft:
        c_l, c_r = st.columns(2)
        with c_l: st.info(st.session_state.g_draft)
        with c_r: st.warning(st.session_state.s_draft)
        
        if st.button("🤝 Merge & Save to History"):
            client = genai.Client(api_key=st.session_state.google_key)
            merge_p = f"Merge these: \n1: {st.session_state.g_draft}\n2: {st.session_state.s_draft}"
            res_m = client.models.generate_content(model='gemini-2.5-flash', contents=merge_p)
            st.session_state.final_master = res_m.text
            # SAVE TO HISTORY
            save_to_history(doc_type, facts, st.session_state.final_master)
            st.success("Saved to Case History!")
            st.rerun()

    if st.session_state.final_master:
        st.divider()
        st.subheader("📜 Master Document")
        st.write(st.session_state.final_master)
        st.download_button("📥 Download Document", st.session_state.final_master, "draft.txt")