import streamlit as st
import os
from google import genai
from docx import Document
import urllib.parse

# 1. SETUP & PATHS
VAULT_PATH = "private_vault"
if not os.path.exists(VAULT_PATH): 
    os.makedirs(VAULT_PATH)

st.set_page_config(page_title="Kerala Senior Advocate Workstation", layout="wide")

# Persistent Session State
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = []

# 2. KEY LOADER (Verified for geminiapikey.py)
def get_verified_key():
    try:
        import geminiapikey
        return geminiapikey.GOOGLE_API_KEY
    except (ImportError, AttributeError):
        # Check system env as a backup
        return os.getenv("GOOGLE_API_KEY")

USER_KEY = get_verified_key()

# 3. UTILITY FUNCTIONS
def read_style_dna(filename):
    try:
        doc = Document(os.path.join(VAULT_PATH, filename))
        # Captures first 20 paragraphs for style without hitting token limits
        return "\n".join([p.text for p in doc.paragraphs[:20]])
    except: return "Error reading style file."

def apply_party_replace(target, replacement):
    if replacement and st.session_state.final_master:
        st.session_state.final_master = st.session_state.final_master.replace(target, replacement)

KERALA_DISTRICTS = ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"]

# 4. SIDEBAR (Verified Features)
with st.sidebar:
    st.title("👨‍⚖️ Kerala Admin")
    
    # API Status Light
    if USER_KEY:
        st.success("🟢 API Connected")
    else:
        st.error("🔴 Key Missing")
        USER_KEY = st.text_input("Manually Paste Key:", type="password")

    doc_type = st.selectbox("Petition Type", ["Bail Application", "NI Act (Cheque)", "Writ Petition", "Maintenance", "Divorce"])
    jurisdiction = st.selectbox("Court Level", ["High Court", "District Court", "Family Court"])
    
    # Kerala HC Logic: Locks district to Ernakulam for HC
    is_hc = (jurisdiction == "High Court")
    selected_district = st.selectbox("District", KERALA_DISTRICTS, 
                                     index=KERALA_DISTRICTS.index("Ernakulam") if is_hc else 0, 
                                     disabled=is_hc)
    
    st.divider()
    draft_tone = st.radio("Strategy:", ["Professional", "Aggressive", "Conciliatory"])
    
    st.divider()
    st.subheader("📂 Style Vault")
    uploaded = st.file_uploader("Upload Winning Doc", type="docx")
    if uploaded:
        with open(os.path.join(VAULT_PATH, uploaded.name), "wb") as f:
            f.write(uploaded.getbuffer())
        st.toast("Document Added to Vault!")
    
    vault_files = os.listdir(VAULT_PATH)
    selected_ref = st.selectbox("Reference Case:", ["None"] + vault_files)
    
    if len(vault_files) > 0:
        with st.expander("🗑️ Manage Vault"):
            for f in vault_files:
                if st.button(f"Delete {f[:12]}...", key=f"del_{f}"):
                    os.remove(os.path.join(VAULT_PATH, f))
                    st.rerun()

# 5. MAIN WORKSTATION (Permanent Buttons)
st.title(f"Drafting: {doc_type}")
facts = st.text_area("Case Facts & Citations:", height=150, placeholder="Enter case summary here...")

# --- THE PERMANENT COMMAND CENTER ---
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("🔍 Search API", use_container_width=True):
        st.session_state.search_results = [{"title": f"Recent {doc_type} Precedents", "desc": "Check IndianKanoon for latest 2026 citations."}]

with c2:
    q = urllib.parse.quote_plus(facts if facts else "Kerala Law")
    st.link_button("🌐 Web Research", f"https://indiankanoon.org/search/?formInput={q}", use_container_width=True)

with c3:
    if st.button("🚀 Standard Draft", use_container_width=True):
        if not USER_KEY: st.error("Add Key first!")
        else:
            with st.spinner("Generating Standard Draft..."):
                client = genai.Client(api_key=USER_KEY)
                court_info = "High Court of Kerala" if is_hc else f"{jurisdiction} at {selected_district}"
                prompt = f"Act as a Kerala Advocate. Draft a {doc_type} for {court_info}. Tone: {draft_tone}. Facts: {facts}. Use PARTY A/B."
                res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                st.session_state.final_master = res.text

with c4:
    mirror_active = (selected_ref != "None")
    if st.button("✨ Mirror Style", type="primary", use_container_width=True, disabled=not mirror_active):
        if not USER_KEY: st.error("Add Key first!")
        else:
            with st.spinner(f"Mimicking {selected_ref}..."):
                client = genai.Client(api_key=USER_KEY)
                dna = read_style_dna(selected_ref)
                prompt = f"MIMIC THIS STYLE:\n{dna}\n\nTASK: Draft a {doc_type}. Tone: {draft_tone}. Facts: {facts}. Use PARTY A/B."
                res = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                st.session_state.final_master = res.text

# 6. EDITOR & PARTY REPLACE
if st.session_state.final_master:
    st.divider()
    st.subheader("📜 Live Editor")
    
    col_a, col_b = st.columns(2)
    with col_a:
        pa = st.text_input("Replace PARTY A with:", placeholder="Petitioner Name")
        if st.button("Set Petitioner"): apply_party_replace("PARTY A", pa); st.rerun()
    with col_b:
        pb = st.text_input("Replace PARTY B with:", placeholder="Respondent Name")
        if st.button("Set Respondent"): apply_party_replace("PARTY B", pb); st.rerun()

    st.session_state.final_master = st.text_area("Final Draft View:", value=st.session_state.final_master, height=600)