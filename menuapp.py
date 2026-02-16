import streamlit as st
import os
import requests
import time
from google import genai
from dotenv import load_dotenv

# 1. AUTHENTICATION & INITIALIZATION
load_dotenv()
INITIAL_G_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
INITIAL_IK_TOKEN = os.getenv("INDIAN_KANOON_TOKEN", "").strip()

# 2. SESSION STATE MANAGEMENT
if "google_key" not in st.session_state: st.session_state.google_key = INITIAL_G_KEY
if "ik_token" not in st.session_state: st.session_state.ik_token = INITIAL_IK_TOKEN
if "ik_balance" not in st.session_state: st.session_state.ik_balance = 500.00
if "g_draft" not in st.session_state: st.session_state.g_draft = ""
if "s_draft" not in st.session_state: st.session_state.s_draft = ""
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = []

# 3. MOCK DATA ENGINE (For Intern Testing)
def get_mock_kanoon_data():
    return [
        {
            "title": "Kesavananda Bharati v. State of Kerala (1973)",
            "docsource": "Supreme Court of India",
            "tid": "123456",
            "headline": "Established the 'Basic Structure Doctrine', limiting Parliament's power to amend the Constitution."
        },
        {
            "title": "Maneka Gandhi v. Union of India (1978)",
            "docsource": "Supreme Court of India",
            "tid": "789101",
            "headline": "Expanded the scope of Article 21 (Right to Life) to include the right to live with dignity."
        }
    ]

# 4. TABS INTERFACE
st.set_page_config(page_title="Legal Workstation", layout="wide")
tab_work, tab_settings = st.tabs(["⚖️ Workstation", "⚙️ Settings"])

# --- TAB 2: SETTINGS (Senior Lawyer's Configuration) ---
with tab_settings:
    st.header("🔑 API Configuration")
    st.info("The Senior Lawyer can paste their Indian Kanoon Token here. It will be saved for this session.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.google_key = st.text_input("Gemini API Key", value=st.session_state.google_key, type="password")
    with col_b:
        st.session_state.ik_token = st.text_input("Indian Kanoon Token", value=st.session_state.ik_token, type="password")
    
    if st.button("💾 Save & Refresh"):
        st.success("Settings applied!")
        st.rerun()

# --- TAB 1: WORKSTATION (Main Interface) ---
with tab_work:
    # Sidebar Status
    with st.sidebar:
        st.title("👨‍⚖️ Status")
        if len(st.session_state.ik_token) > 5:
            st.success("🟢 Senior Mode: Live")
            st.metric("IK Balance", f"₹{st.session_state.ik_balance:.2f}")
        else:
            st.warning("🧪 Intern Mode: Mocking")
            st.caption("No token found. Using simulated case data.")
        
        st.divider()
        st.caption("Powered by IKanoon")

    st.title("⚖️ Legal Workstation")
    prompt = st.text_area("Legal Prompt / Facts of the Case:", placeholder="Enter the details here...", height=120)

    # ACTION BUTTONS
    c1, c2, _ = st.columns([1, 1, 3])
    
    with c1:
        if st.button("🔍 Search Precedents", use_container_width=True):
            if not prompt:
                st.warning("Please enter facts first.")
            elif len(st.session_state.ik_token) < 5:
                # INTERN MODE
                st.session_state.search_results = get_mock_kanoon_data()
                st.toast("Generated Mock Results")
            else:
                # SENIOR MODE (Live API Call)
                try:
                    headers = {'Authorization': f'Token {st.session_state.ik_token}'}
                    res = requests.post(f"https://api.indiankanoon.org/search/?formInput={prompt}", headers=headers)
                    if res.status_code == 200:
                        st.session_state.search_results = res.json().get('docs', [])
                        st.session_state.ik_balance -= 0.50
                    else:
                        st.error(f"API Error: {res.status_code}")
                except Exception as e:
                    st.error(f"Connection Failed: {e}")

    with c2:
        if st.button("🚀 Draft Document", type="primary", use_container_width=True):
            if not st.session_state.google_key:
                st.error("Please add Gemini Key in Settings!")
            else:
                client = genai.Client(api_key=st.session_state.google_key)
                with st.spinner("Gemini drafting..."):
                    # Phase A: Primary Draft
                    res_g = client.models.generate_content(model='gemini-2.0-flash', contents=f"Draft a legal response for: {prompt}")
                    st.session_state.g_draft = res_g.text
                    # Phase B: Adversarial
                    res_s = client.models.generate_content(model='gemini-2.0-flash', contents=f"Provide legal risks for: {prompt}")
                    st.session_state.s_draft = res_s.text

    # DISPLAY RESULTS
    if st.session_state.search_results:
        with st.expander("📚 Relevant Case Laws Found", expanded=True):
            for doc in st.session_state.search_results[:3]:
                st.markdown(f"**{doc.get('title')}** | {doc.get('docsource')}")
                st.write(doc.get('headline'))
                st.divider()

    if st.session_state.g_draft:
        st.divider()
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Draft A (Primary)")
            st.info(st.session_state.g_draft)
        with col_right:
            st.subheader("Draft B (Risks)")
            st.success(st.session_state.s_draft)

        if st.button("🤝 Merge into Master Draft"):
            client = genai.Client(api_key=st.session_state.google_key)
            with st.spinner("Synthesizing..."):
                merge_text = f"Merge these into one master draft:\n1: {st.session_state.g_draft}\n2: {st.session_state.s_draft}"
                res_m = client.models.generate_content(model='gemini-2.0-flash', contents=merge_text)
                st.session_state.final_master = res_m.text

    if st.session_state.final_master:
        st.divider()
        st.markdown("### 📜 Final Master Version")
        st.write(st.session_state.final_master)