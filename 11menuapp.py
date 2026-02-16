import streamlit as st
import os
import requests
import pandas as pd
from datetime import datetime
from google import genai
from docx import Document
import io
import urllib.parse

# 1. DIRECTORY SETUP
VAULT_PATH = "private_vault"
if not os.path.exists(VAULT_PATH): os.makedirs(VAULT_PATH)

st.set_page_config(page_title="Kerala Senior Advocate Workstation", layout="wide")

# Persistent Session State
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = []

# 2. UTILITY FUNCTIONS
def read_vault_dna(filename):
    """Extracts linguistic style from vault documents."""
    try:
        doc = Document(os.path.join(VAULT_PATH, filename))
        return "\n".join([p.text for p in doc.paragraphs[:25]])
    except: return ""

def apply_replace(target, replacement):
    """Updates the draft in real-time."""
    if replacement and st.session_state.final_master:
        st.session_state.final_master = st.session_state.final_master.replace(target, replacement)

KERALA_DISTRICTS = ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"]

# 3. SIDEBAR (Vault Management & Settings)
with st.sidebar:
    st.title("👨‍⚖️ Kerala Admin")
    doc_type = st.selectbox("Petition Type", ["Bail Application", "NI Act (Cheque)", "Writ Petition", "Maintenance", "Divorce Petition"])
    jurisdiction = st.selectbox("Court Level", ["High Court", "District Court", "Family Court"])
    
    # KERALA HC LOGIC
    is_hc = (jurisdiction == "High Court")
    selected_district = st.selectbox("District", KERALA_DISTRICTS, 
                                     index=KERALA_DISTRICTS.index("Ernakulam") if is_hc else 0, 
                                     disabled=is_hc)
    
    st.divider()
    st.subheader("🎭 Drafting Strategy")
    draft_tone = st.radio("Tone:", ["Professional", "Aggressive", "Conciliatory"])
    
    st.divider()
    st.subheader("📤 Vault Manager")
    uploaded = st.file_uploader("Upload Winning Doc (.docx)", type="docx")
    if uploaded:
        with open(os.path.join(VAULT_PATH, uploaded.name), "wb") as f: f.write(uploaded.getbuffer())
        st.success("File added to vault!")
    
    vault_files = os.listdir(VAULT_PATH)
    selected_ref = st.selectbox("Style Reference:", ["None"] + vault_files)
    
    if len(vault_files) > 0:
        with st.expander("🗑️ Delete from Vault"):
            for f in vault_files:
                if st.button(f"Delete {f[:15]}...", key=f"del_{f}"):
                    os.remove(os.path.join(VAULT_PATH, f))
                    st.rerun()

# 4. MAIN WORKSTATION
st.title(f"Drafting Station: {doc_type}")
facts = st.text_area("Case Facts:", height=150, placeholder="Paste facts or summary here...", key="facts_main")

# --- PERMANENT COMMAND CENTER (Disappearing Fix) ---
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("🔍 Search API", use_container_width=True):
        # Placeholder for your Indian Kanoon API integration
        st.session_state.search_results = [{"title": "Kerala HC Precedent 2024", "desc": "Example case result."}]

with c2:
    query = urllib.parse.quote_plus(facts if facts else "Kerala High Court")
    st.link_button("🌐 Web Research", f"https://indiankanoon.org/search/?formInput={query}", use_container_width=True)

with c3:
    if st.button("🚀 Standard Draft", use_container_width=True):
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        court_label = "HIGH COURT OF KERALA" if is_hc else f"{jurisdiction.upper()} AT {selected_district.upper()}"
        prompt = f"Draft {doc_type} for {court_label}. Tone: {draft_tone}. Facts: {facts}. Use PARTY A/B."
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        st.session_state.final_master = res.text

with c4:
    mirror_on = (selected_ref != "None")
    if st.button("✨ Mirror Style", type="primary", use_container_width=True, disabled=not mirror_on):
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        dna = read_vault_dna(selected_ref)
        prompt = f"MIMIC THIS STYLE:\n{dna}\n\nTASK: Draft {doc_type}. Tone: {draft_tone}. Facts: {facts}. Use PARTY A/B."
        res = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        st.session_state.final_master = res.text

# 5. RESULTS & EDITOR
if st.session_state.search_results:
    with st.expander("📚 Case Law References"):
        for res in st.session_state.search_results: st.markdown(f"**{res['title']}** - {res['desc']}")

if st.session_state.final_master:
    st.divider()
    st.subheader("📜 Live Editor & Party Mapping")
    col_a, col_b = st.columns(2)
    with col_a:
        p_name = st.text_input("Petitioner Name:", key="pa")
        if st.button("Apply Party A"): apply_replace("PARTY A", p_name); st.rerun()
    with col_b:
        r_name = st.text_input("Respondent Name:", key="rb")
        if st.button("Apply Party B"): apply_replace("PARTY B", r_name); st.rerun()

    st.session_state.final_master = st.text_area("Final Edit:", value=st.session_state.final_master, height=600)