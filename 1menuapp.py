import streamlit as st
import os
import requests
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# 1. INITIAL SETUP & KEYS
load_dotenv()
INITIAL_G_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
INITIAL_IK_TOKEN = os.getenv("INDIAN_KANOON_TOKEN", "").strip()
HISTORY_FILE = "case_history.csv"

st.set_page_config(page_title="Legal Master Workstation", layout="wide")

# 2. SESSION STATE MANAGEMENT
if "google_key" not in st.session_state: st.session_state.google_key = INITIAL_G_KEY
if "ik_token" not in st.session_state: st.session_state.ik_token = INITIAL_IK_TOKEN
if "ik_balance" not in st.session_state: st.session_state.ik_balance = 500.00
if "g_draft" not in st.session_state: st.session_state.g_draft = ""
if "s_draft" not in st.session_state: st.session_state.s_draft = ""
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = []

# 3. SMART MOCK DATABASE (Filtered by Type & Jurisdiction)
MOCK_DATABASE = [
    {"title": "Niklesh Prakash Patil v. State of Maharashtra", "type": "Bail Application", "jurisdiction": "High Court", "headline": "Parity in bail matters under Article 21."},
    {"title": "Satender Kumar Antil v. CBI", "type": "Bail Application", "jurisdiction": "High Court", "headline": "New guidelines for arrest and bail procedures."},
    {"title": "Dashrath Rupsingh Rathod v. Maharashtra", "type": "Legal Notice", "jurisdiction": "District Court", "headline": "Territorial jurisdiction for NI Act complaints."},
    {"title": "MSR Leathers v. S. Palaniappan", "type": "Legal Notice", "jurisdiction": "District Court", "headline": "Validity of multiple presentations of a cheque."},
    {"title": "Rajnesh v. Neha (2020)", "type": "Maintenance Petition", "jurisdiction": "Family Court", "headline": "Mandatory disclosure of assets for maintenance."},
    {"title": "Shah Bano Begum v. Mohd. Ahmad Khan", "type": "Maintenance Petition", "jurisdiction": "Family Court", "headline": "Right of maintenance under Section 125 CrPC."},
    {"title": "Amrita Singh v. Ratan Singh", "type": "Divorce Petition", "jurisdiction": "Family Court", "headline": "Maintenance rights during matrimonial disputes."}
]

# 4. UTILITY FUNCTIONS
def save_to_history(case_type, facts, draft):
    new_data = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Type": case_type, "Facts": facts[:50], "Full_Draft": draft}])
    if not os.path.isfile(HISTORY_FILE):
        new_data.to_csv(HISTORY_FILE, index=False)
    else:
        new_data.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

def get_history():
    return pd.read_csv(HISTORY_FILE) if os.path.exists(HISTORY_FILE) else pd.DataFrame()

def get_filtered_mock(doc_type, court):
    res = [c for c in MOCK_DATABASE if c["type"] == doc_type and c["jurisdiction"] == court]
    return res if res else [{"title": "No Mock Match", "court": "N/A", "headline": "Try a different combination for mock data."}]

# 5. TABS INTERFACE
tab_work, tab_settings = st.tabs(["⚖️ Workstation", "⚙️ Settings"])

# --- TAB: SETTINGS ---
with tab_settings:
    st.header("🔑 API Configuration")
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.google_key = st.text_input("Gemini API Key", value=st.session_state.google_key, type="password")
    with col_b:
        st.session_state.ik_token = st.text_input("Indian Kanoon Token", value=st.session_state.ik_token, type="password")
    if st.button("💾 Save Settings"):
        st.rerun()

# --- TAB: WORKSTATION ---
with tab_work:
    with st.sidebar:
        st.title("👨‍⚖️ Admin")
        doc_type = st.selectbox("Document Type", ["Bail Application", "Legal Notice", "Maintenance Petition", "Divorce Petition", "Writ Petition"])
        jurisdiction = st.selectbox("Jurisdiction", ["High Court", "District Court", "Family Court"])
        tone = st.radio("Tone", ["Professional & Firm", "Aggressive", "Conciliatory"])
        st.divider()
        st.subheader("📜 History")
        hist = get_history()
        if not hist.empty:
            for i, row in hist.tail(3).iterrows():
                if st.button(f"📄 {row['Type']} ({row['Date']})", key=f"h_{i}"):
                    st.session_state.final_master = row['Full_Draft']
        
        st.divider()
        if len(st.session_state.ik_token) > 5:
            st.success("🟢 Senior Mode: Live")
            st.metric("Balance", f"₹{st.session_state.ik_balance:.2f}")
        else:
            st.warning("🧪 Intern Mode: Mocking")

    st.title(f"⚖️ {doc_type} Draft")
    facts = st.text_area("Case Facts:", placeholder="Describe the client's situation...", height=150)

    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        if st.button("🔍 Search Cases", use_container_width=True):
            if len(st.session_state.ik_token) < 5:
                st.session_state.search_results = get_filtered_mock(doc_type, jurisdiction)
            else:
                try:
                    headers = {'Authorization': f'Token {st.session_state.ik_token}'}
                    url = f"https://api.indiankanoon.org/search/?formInput={facts}"
                    r = requests.post(url, headers=headers)
                    if r.status_code == 200:
                        st.session_state.search_results = r.json().get('docs', [])
                        st.session_state.ik_balance -= 0.50
                except: st.error("API Connection Error")
            st.rerun()

    with c2:
        if st.button("🚀 Draft Document", type="primary", use_container_width=True):
            if not st.session_state.google_key:
                st.error("Missing Gemini Key!")
            else:
                try:
                    client = genai.Client(api_key=st.session_state.google_key)
                    with st.status("Analyzing...", expanded=False):
                        st.write("Drafting...")
                        res_g = client.models.generate_content(model='gemini-2.5-flash', contents=f"Draft {doc_type} in {jurisdiction} tone {tone}. Facts: {facts}")
                        st.session_state.g_draft = res_g.text
                        st.write("Finding Risks...")
                        res_s = client.models.generate_content(model='gemini-2.5-flash', contents=f"Risks for: {facts}")
                        st.session_state.s_draft = res_s.text
                    st.rerun()
                except Exception as e:
                    if "429" in str(e): st.error("🚦 Rate Limit: Wait 60s")
                    else: st.error(f"Error: {e}")

    if st.session_state.search_results:
        with st.expander("📚 Precedents Found", expanded=True):
            for doc in st.session_state.search_results[:2]:
                st.markdown(f"**{doc.get('title')}**")
                st.caption(doc.get('headline'))
                st.divider()

    if st.session_state.g_draft:
        cl, cr = st.columns(2)
        with cl: st.info(st.session_state.g_draft)
        with cr: st.warning(st.session_state.s_draft)
        if st.button("🤝 Merge & Save"):
            client = genai.Client(api_key=st.session_state.google_key)
            m = client.models.generate_content(model='gemini-2.5-flash', contents=f"Merge: \n1: {st.session_state.g_draft}\n2: {st.session_state.s_draft}")
            st.session_state.final_master = m.text
            save_to_history(doc_type, facts, st.session_state.final_master)
            st.rerun()

    if st.session_state.final_master:
        st.divider()
        st.write(st.session_state.final_master)
        st.download_button("📥 Download", st.session_state.final_master, "draft.txt")