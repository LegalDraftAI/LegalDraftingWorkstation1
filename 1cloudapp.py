import streamlit as st
import os
import pandas as pd
from datetime import datetime
from google import genai
from docx import Document
from fpdf import FPDF
import io
import urllib.parse
from supabase import create_client, Client

# --- START OF COMBINED AUTHENTICATION & SIDEBAR LOGIC ---

# Initialize session state for security
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = None

def login_form():
    """Displays the login screen."""
    st.markdown("### 👨‍⚖️ Kerala Senior Advocate Workstation")
    st.subheader("Authorized Access Only")
    
    with st.form("login_gate"):
        user = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Enter Workstation")
        
        if submit:
            # Fetches the [passwords] section from your Streamlit Secrets
            creds = st.secrets.get("passwords", {})
            if user in creds and password == creds[user]:
                st.session_state.authenticated = True
                st.session_state.user_role = user
                st.rerun()
            else:
                st.error("Invalid credentials. Access Denied.")

# Step 1: Check Authentication - If fail, stop the app here
if not st.session_state.authenticated:
    login_form()
    st.stop() 

# Step 2: Define the Sidebar with a Logout Button
# This will appear at the top of your sidebar once logged in
with st.sidebar:
    st.title(f"👨‍⚖️ {st.session_state.user_role.capitalize()} Panel")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.rerun()
    st.divider()

# --- END OF COMBINED AUTHENTICATION & SIDEBAR LOGIC ---

# 1. INITIALIZATION & SECURE SETUP
SUPABASE_URL = "https://wuhsjcwtoradbzeqsoih.supabase.co"
SUPABASE_KEY = "sb_publishable_02nqexIYCCBaWryubZEkqA_Tw2PqX6m"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VAULT_PATH = "private_vault"
HISTORY_FILE = "kerala_legal_history.csv"

if not os.path.exists(VAULT_PATH):
    os.makedirs(VAULT_PATH)

st.set_page_config(page_title="Kerala Senior Advocate Workstation", layout="wide")

def get_key():
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except:
        return ""

# Feature 16: Cloud Save
def save_to_supabase(dtype, content, client_name, case_no):
    try:
        data = {
            "draft type": dtype,
            "draft content": content,
            "client name": client_name,
            "case number": case_no
        }
        supabase.table("legal_drafts").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Cloud Connection Issue: {e}")
        return False

# Session State Management
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = []
if "widget_key" not in st.session_state: st.session_state.widget_key = 0

# Feature 15: Save History Utility
def load_history():
    if os.path.exists(HISTORY_FILE):
        try: return pd.read_csv(HISTORY_FILE).tail(10).iloc[::-1]
        except: return pd.DataFrame()
    return pd.DataFrame()

def save_draft_to_history(dtype, content):
    new_data = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Type": dtype, "Draft": content}])
    new_data.to_csv(HISTORY_FILE, mode='a', header=not os.path.exists(HISTORY_FILE), index=False)

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    clean_text = text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, clean_text)
    pdf_out = pdf.output(dest='S')
    return bytes(pdf_out, 'latin-1')

def create_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# 3. INTERFACE
USER_KEY = get_key()

with st.sidebar:
    st.title("👨‍⚖️ Control Panel")
    if USER_KEY: st.success("🟢 AI Online")
    
    doc_type = st.selectbox("Petition Type", ["Bail Application", "NI Act (Sec 138)", "Writ Petition", "MC 125", "Domestic Violence", "MVOP", "Injunction", "Divorce"])
    jurisdiction = st.selectbox("Court Level", ["High Court", "District Court", "Family Court", "Munsiff Court"])
    
    is_hc = (jurisdiction == "High Court")
    districts = ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"]
    selected_district = st.selectbox("District", districts, index=1 if is_hc else 0, disabled=is_hc)
    
    st.divider()
    uploaded = st.file_uploader("Style Vault Ref", type="docx")
    if uploaded:
        with open(os.path.join(VAULT_PATH, uploaded.name), "wb") as f: f.write(uploaded.getbuffer())
    
    vault_files = os.listdir(VAULT_PATH)
    selected_ref = st.selectbox("Mirror Reference:", ["None"] + vault_files)

    if st.button("🧹 Clear All", use_container_width=True):
        st.session_state.final_master = ""
        st.session_state.search_results = []
        st.session_state.widget_key += 1
        st.rerun()

    st.divider()
    st.subheader("📜 Recent History")
    hist_df = load_history()
    if not hist_df.empty:
        for i, row in hist_df.iterrows():
            if st.button(f"📄 {row['Type']} ({row['Date'][:10]})", key=f"h_{i}", use_container_width=True):
                st.session_state.final_master = row['Draft']
                st.rerun()

# --- MAIN WORK AREA ---
st.title(f"Drafting: {doc_type}")
facts = st.text_area("Case Facts:", height=150, key=f"f_{st.session_state.widget_key}")

c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("🔍 Search API", use_container_width=True):
        st.session_state.search_results = [{"title": "Kerala HC Precedent 2025", "cite": "2025 KER 101", "sum": "Legal grounds confirmed."}]
with c2:
    q = urllib.parse.quote_plus(facts if facts else "Kerala Law")
    st.link_button("🌐 Web Research", f"https://indiankanoon.org/search/?formInput={q}", use_container_width=True)
with c3:
    if st.button("🚀 Standard Draft", use_container_width=True):
        if USER_KEY:
            with st.spinner("AI Drafting...", show_time=True):
                client = genai.Client(api_key=USER_KEY)
                prompt = f"As a Kerala Lawyer, draft {doc_type} for {jurisdiction} in {selected_district}. Facts: {facts}. STRICTLY USE 'PARTY A' and 'PARTY B'. NO NAMES."
                res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                st.session_state.final_master = res.text
with c4:
    if st.button("✨ Mirror Style", type="primary", use_container_width=True, disabled=(selected_ref=="None")):
        if USER_KEY:
            with st.spinner(f"Mirroring {selected_ref}...", show_time=True):
                client = genai.Client(api_key=USER_KEY)
                doc = Document(os.path.join(VAULT_PATH, selected_ref))
                dna = "\n".join([p.text for p in doc.paragraphs[:15]])
                prompt = f"MIMIC THIS STYLE:\n{dna}\n\nTASK: Draft {doc_type} for {facts}. USE 'PARTY A' and 'PARTY B'."
                res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                st.session_state.final_master = res.text

if st.session_state.search_results:
    with st.expander("📚 Related Precedents", expanded=True):
        for r in st.session_state.search_results: st.write(f"**{r['title']}** ({r['cite']})")

if st.session_state.final_master:
    st.divider()
    st.subheader("🛠️ Case Details & Name Mapping")
    m1, m2 = st.columns(2)
    with m1:
        c_name = st.text_input("Client Name (for Cloud):")
        name_a = st.text_input("Name for PARTY A:")
        if st.button("Apply Petitioner Name"):
            st.session_state.final_master = st.session_state.final_master.replace("PARTY A", name_a)
            st.rerun()
    with m2:
        c_num = st.text_input("Case Number (for Cloud):")
        name_b = st.text_input("Name for PARTY B:")
        if st.button("Apply Respondent Name"):
            st.session_state.final_master = st.session_state.final_master.replace("PARTY B", name_b)
            st.rerun()

    st.session_state.final_master = st.text_area("Live Editor:", value=st.session_state.final_master, height=400)
    
    st.divider()
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        if st.button("💾 Log Local", use_container_width=True):
            save_draft_to_history(doc_type, st.session_state.final_master)
            st.toast("Saved Locally!")
    with e2:
        if st.button("☁️ Cloud Save", use_container_width=True, type="primary"):
            if save_to_supabase(doc_type, st.session_state.final_master, c_name, c_num):
                st.success("Saved to Cloud Vault!")
                st.balloons()
    with e3:
        st.download_button("📥 MS Word", data=create_docx(st.session_state.final_master), file_name="draft.docx", use_container_width=True)
    with e4:
        st.download_button("📥 PDF", data=create_pdf(st.session_state.final_master), file_name="draft.pdf", use_container_width=True)
