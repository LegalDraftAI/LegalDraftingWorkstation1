import streamlit as st
import os
import time
from google import genai
from dotenv import load_dotenv

# 1. CLEAN AUTHENTICATION
load_dotenv()
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

# Initialize Google Client
client_google = genai.Client(api_key=GOOGLE_KEY)

st.set_page_config(page_title="Master Workstation", layout="wide")
st.title("⚖️ Legal Workstation (Gemini 2.5 Only)")

# 2. SESSION STATE
if "g_draft" not in st.session_state: st.session_state.g_draft = ""
if "s_draft" not in st.session_state: st.session_state.s_draft = ""
if "final_master" not in st.session_state: st.session_state.final_master = ""

# 3. INPUT
prompt = st.text_area("Legal Prompt:", placeholder="Enter your instructions...", height=100)

if st.button("🚀 Run Analysis", type="primary"):
    if not prompt:
        st.warning("Please enter a prompt.")
    else:
        # A. GOOGLE (Primary Draft)
        with st.spinner("Consulting Gemini 2.5 (Primary)..."):
            try:
                # Primary call: Standard legal drafting
                res_g = client_google.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=f"Draft a legal response for: {prompt}"
                )
                st.session_state.g_draft = res_g.text
            except Exception as e:
                st.error(f"Primary Error: {e}")

        # B. GOOGLE (Secondary Opinion)
        with st.spinner("Consulting Gemini 2.5 (Adversarial View)..."):
            try:
                # Secondary call: Critiquing or alternative perspective
                res_s = client_google.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=f"Provide a critical legal counter-perspective or alternative clauses for: {prompt}"
                )
                st.session_state.s_draft = res_s.text
            except Exception as e:
                st.error(f"Secondary Error: {e}")

# 4. DISPLAY & MERGE
if st.session_state.g_draft or st.session_state.s_draft:
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Draft A (Primary)")
        if st.session_state.g_draft:
            st.info(st.session_state.g_draft)
        else:
            st.write("Waiting for primary draft...")
            
    with c2:
        st.subheader("Draft B (Secondary)")
        if st.session_state.s_draft:
            st.success(st.session_state.s_draft)
        else:
            st.write("Waiting for secondary draft...")

    if st.button("🤝 Merge Best Clauses (using Gemini 2.5)"):
        with st.spinner("Merging..."):
            # Breather for stability
            time.sleep(5)
            merge_text = f"As a Senior Lawyer, merge these two perspectives into one master draft. Ensure all risks are covered:\n1: {st.session_state.g_draft}\n2: {st.session_state.s_draft}"
            try:
                res_m = client_google.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=merge_text
                )
                st.session_state.final_master = res_m.text
            except Exception as e:
                st.error(f"Merge Error: {e}. Please wait a moment and try again.")

if st.session_state.final_master:
    st.divider()
    st.markdown("### 📜 Final Master Version")
    st.write(st.session_state.final_master)
    st.download_button("📥 Download Master Draft", st.session_state.final_master, "master_draft.txt")