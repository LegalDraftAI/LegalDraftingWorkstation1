import streamlit as st
import os
import time
from google import genai
from openai import OpenAI
from dotenv import load_dotenv

# 1. CLEAN AUTHENTICATION
load_dotenv()
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
OR_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

client_google = genai.Client(api_key=GOOGLE_KEY)
client_or = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OR_KEY,
)

st.set_page_config(page_title="Master Workstation", layout="wide")
st.title("⚖️ Legal Workstation (Gemini 2.5 Primary)")

# 2. SESSION STATE
if "g_draft" not in st.session_state: st.session_state.g_draft = ""
if "s_draft" not in st.session_state: st.session_state.s_draft = ""
if "final_master" not in st.session_state: st.session_state.final_master = ""

# 3. INPUT
prompt = st.text_area("Legal Prompt:", placeholder="Enter your instructions...", height=100)

if st.button("🚀 Run Comparison", type="primary"):
    if not prompt:
        st.warning("Please enter a prompt.")
    else:
        # A. GOOGLE (Primary Draft)
        with st.spinner("Consulting Gemini 2.5..."):
            try:
                res_g = client_google.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                st.session_state.g_draft = res_g.text
            except Exception as e:
                st.error(f"Google Error: {e}")

        # B. OPENROUTER (Secondary Comparison)
        with st.spinner("Finding Secondary AI..."):
            try:
                res_s = client_or.chat.completions.create(
                    model="openrouter/free", 
                    messages=[{"role": "user", "content": prompt}]
                )
                st.session_state.s_draft = res_s.choices[0].message.content
            except Exception as e:
                st.error(f"Secondary AI Error: {e}")

# 4. DISPLAY & MERGE
if st.session_state.g_draft or st.session_state.s_draft:
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Draft A (Google Gemini)")
        st.info(st.session_state.g_draft if st.session_state.g_draft else "Waiting for Google...")
    with c2:
        st.subheader("Draft B (Secondary Opinion)")
        st.success(st.session_state.s_draft if st.session_state.s_draft else "Secondary AI busy...")

    if st.button("🤝 Merge Best Clauses (using Gemini)"):
        with st.spinner("Merging..."):
            # Mandatory 5-second breather for Gemini Free Tier stability
            time.sleep(5)
            merge_text = f"As a Senior Lawyer, merge these into one master draft:\n1: {st.session_state.g_draft}\n2: {st.session_state.s_draft}"
            try:
                # Using Gemini for the Merge because it's the 'Brain'
                res_m = client_google.models.generate_content(model='gemini-2.0-flash', contents=merge_text)
                st.session_state.final_master = res_m.text
            except Exception as e:
                st.error(f"Merge Error: {e}. Please wait 60 seconds and try again.")

if st.session_state.final_master:
    st.divider()
    st.markdown("### 📜 Final Master Version")
    st.write(st.session_state.final_master)
    st.download_button("📥 Download Master Draft", st.session_state.final_master, "master_draft.txt")