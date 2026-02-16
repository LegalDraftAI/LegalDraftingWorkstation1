import streamlit as st
import os
import pandas as pd
from datetime import datetime
from google import genai
from docx import Document
from fpdf import FPDF
import io
import urllib.parse

# 1. PATH & DIRECTORY SETUP
VAULT_PATH = "private_vault"
if not os.path.exists(VAULT_PATH):
    os.makedirs(VAULT_PATH)

st.set_page_config(page_title="Kerala Senior Advocate Workstation", layout="wide")

# Persistent State Initialization
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "vault_files" not in st.session_state: st.session_state.vault_files = os.listdir(VAULT_PATH)
if "search_results" not in st.session_state: st.session_state.search_results = []

# 2. CORE UTILITIES
def read_docx_dna(file_path):
    """Extracts the first 30 paragraphs to capture linguistic style."""
    try:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs[:30]])
    except Exception: return ""

def apply_smart_replace(target, replacement):
    """Updates the draft in session state instantly."""
    if replacement and st.session_state.final_master:
        st.session_state.final_master = st.session_state.final_master.replace(target, replacement)

KERALA_DISTRICTS = ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"]

# 3. SIDEBAR: VAULT & CONFIG
with st.sidebar:
    st.title("👨‍⚖️ Kerala Admin")
    doc_type = st.selectbox("Petition Type", ["Bail Application", "NI Act (Cheque)", "Writ Petition", "Maintenance", "Divorce Petition"])
    jurisdiction = st.selectbox("Court Level", ["High Court", "District Court", "Family Court"])
    is_hc = (jurisdiction == "High Court")
    selected_district = st.selectbox("Select District", KERALA_DISTRICTS, index=KERALA_DISTRICTS.index("Ernakulam") if is_hc else 0, disabled=is_hc)
    
    st.divider()
    st.subheader("🎭 Drafting Strategy")
    draft_tone = st.radio("Tone:", ["Professional", "Aggressive", "Conciliatory"])
    
    st.divider()
    st.subheader("📤 Vault Manager")
    uploaded_file = st.file_uploader("Add Winning Petition (.docx)", type="docx")
    if uploaded_file:
        with open(os.path.join(VAULT_PATH, uploaded_file.name), "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.vault_files = os.listdir(VAULT_PATH)
        st.success(f"Added {uploaded_file.name} to Vault!")

    if st.session_state.vault_files:
        with st.expander("📂 Manage Vault Files"):
            for f in st.session_state.vault_files:
                col_name, col_del = st.columns([3, 1])
                col_name.caption(f)
                if col_del.button("🗑️", key=f"del_{f}"):
                    os.remove(os.path.join(VAULT_PATH, f))
                    st.session_state.vault_files = os.listdir(VAULT_PATH)
                    st.rerun()

# 4. MAIN WORKSTATION
st.title(f"Drafting Station: {doc_type}")
facts = st.text_area("Case Facts:", height=150, placeholder="Paste facts, evidence, or citations here...")

c1, c2, c3 = st.columns([1, 1, 1])

with c1:
    if st.button("🚀 Standard Draft", use_container_width=True):
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        court_info = "KERALA HIGH COURT" if is_hc else f"{jurisdiction.upper()} at {selected_district.upper()}"
        prompt = f"Act as a Senior Kerala Advocate. Draft a {doc_type} for {court_info}. Tone: {draft_tone}. Facts: {facts}. Use PARTY A and PARTY B."
        res = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        st.session_state.final_master = res.text

with c2:
    selected_ref = st.selectbox("Style Reference:", ["None"] + st.session_state.vault_files, label_visibility="collapsed")
    if selected_ref != "None":
        if st.button("✨ Mirror Style & Re-Draft", type="primary", use_container_width=True):
            client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
            style_dna = read_docx_dna(os.path.join(VAULT_PATH, selected_ref))
            prompt = f"MIMIC THIS STYLE:\n{style_dna}\n\nTASK: Draft a {doc_type}. Tone: {draft_tone}. Facts: {facts}. Use PARTY A/B."
            res = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
            st.session_state.final_master = res.text

with c3:
    if facts:
        search_query = urllib.parse.quote_plus(f"{facts} Kerala High Court judgment")
        st.link_button("🌐 Web Research", f"https://www.google.com/search?q={search_query}", use_container_width=True)

# 5. EDITOR & PARTY REPLACE
if st.session_state.final_master:
    st.divider()
    st.subheader("📜 Live Editor & Party Mapping")
    
    r1c1, r1c2, r1c3 = st.columns([1, 2, 1])
    with r1c1: st.markdown("**Petitioner:**")
    with r1c2: p_name = st.text_input("Name", placeholder="Replace PARTY A", key="pa", label_visibility="collapsed")
    with r1c3: 
        if st.button("🔄 Apply A", use_container_width=True): apply_smart_replace("PARTY A", p_name); st.rerun()

    r2c1, r2c2, r2c3 = st.columns([1, 2, 1])
    with r2c1: st.markdown("**Respondent:**")
    with r2c2: r_name = st.text_input("Name", placeholder="Replace PARTY B", key="pb", label_visibility="collapsed")
    with r2c3: 
        if st.button("🔄 Apply B", use_container_width=True): apply_smart_replace("PARTY B", r_name); st.rerun()

    st.session_state.final_master = st.text_area("Final Draft View:", value=st.session_state.final_master, height=600)