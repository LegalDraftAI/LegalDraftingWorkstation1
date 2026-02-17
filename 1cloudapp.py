import streamlit as st
import os, io, urllib.parse, time
from datetime import datetime
from google import genai
from docx import Document
from fpdf import FPDF
from supabase import create_client, Client

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="Kerala Senior Advocate Workstation", layout="wide")

# Persistent state for all 19 requirements
DEFAULTS = {
    "authenticated": False, "user_role": None, "final_master": "", 
    "draft_history": [], "facts_input": "", "selected_model": "gemini-2.0-flash"
}
for key, val in DEFAULTS.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 2. CLOUD & LOCAL STORAGE ---
SUPABASE_URL = "https://wuhsjcwtoradbzeqsoih.supabase.co"
SUPABASE_KEY = "sb_publishable_02nqexIYCCBaWryubZEkqA_Tw2PqX6m"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
VAULT_PATH = "private_vault"
if not os.path.exists(VAULT_PATH): os.makedirs(VAULT_PATH)

# --- 3. THE SMART ROTATOR (Req #18) ---
def smart_rotate_draft(prompt):
    projects = st.secrets.get("API_KEYS", [])
    if not projects: return None, "Secrets Error: API_KEYS list missing."
    
    for name, key in projects:
        try:
            client = genai.Client(api_key=key)
            # Req #13: Timer is handled by the calling UI spinner
            res = client.models.generate_content(
                model=st.session_state.selected_model, 
                contents=prompt
            )
            return res.text, name
        except Exception as e:
            if "429" in str(e): # Quota Hit
                st.toast(f"⚠️ Project {name} full. Swapping...")
                continue
            return None, f"Error in {name}: {str(e)}"
    return None, "All 5 Project Quotas Exhausted."

# --- 4. LOGIN GATE (Req #17) ---
if not st.session_state.authenticated:
    st.title("👨‍⚖️ Senior Advocate Workstation")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Access Workstation"):
            creds = st.secrets.get("passwords", {})
            if u in creds and p == creds[u]:
                st.session_state.authenticated = True
                st.session_state.user_role = u
                st.rerun()
            else: st.error("Access Denied")
    st.stop()

# --- 5. SIDEBAR: HISTORY & VAULT (Req #5, #8, #19) ---
with st.sidebar:
    st.subheader(f"Advocate: {st.session_state.user_role.upper()}")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False; st.rerun()
    
    st.divider()
    st.subheader("📜 History (Last 10)")
    for i, item in enumerate(st.session_state.draft_history):
        if st.button(item["label"], key=f"h_{i}", use_container_width=True):
            st.session_state.final_master = item["content"]
            st.rerun()

    st.divider()
    st.session_state.selected_model = st.radio("Intelligence Level:", ["gemini-2.0-flash", "gemini-2.0-pro-exp-02-05"])
    
    st.divider()
    uploaded = st.file_uploader("Upload Style Reference (.docx)", type="docx")
    if uploaded:
        with open(os.path.join(VAULT_PATH, uploaded.name), "wb") as f: f.write(uploaded.getbuffer())
    selected_ref = st.selectbox("Style Mirror:", ["None"] + os.listdir(VAULT_PATH))

# --- 6. MAIN TERMINAL (Req #3, #4, #7, #9, #13, #14) ---
st.header("Drafting Terminal")
col1, col2 = st.columns(2)
with col1:
    court = st.selectbox("Court Level", ["High Court", "District Court", "Family Court", "Munsiff Court", "DVC", "MC", "MVOP"])
    dtype = st.selectbox("Document Type", ["Bail Application", "NI Act 138", "Writ Petition", "OS (Civil)", "Notice"])
with col2:
    dists = ["Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad", "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod"]
    # Req #4: HC Auto-Lock
    target_dist = "Ernakulam" if court == "High Court" else st.selectbox("District", dists)

facts = st.text_area("Case Facts:", value=st.session_state.facts_input, height=150)

# Req #7: Web Research Link
if facts:
    q = urllib.parse.quote(f"{dtype} {facts[:40]} Kerala Court")
    st.markdown(f"🔍 [Research Precedents on Indian Kanoon](https://indiankanoon.org/search/?formInput={q})")

b1, b2, b3 = st.columns([1,1,1])
with b1:
    if st.button("🚀 Draft Standard", type="primary", use_container_width=True):
        p = f"Draft {dtype} for {court} at {target_dist}. Facts: {facts}. USE 'PARTY A' and 'PARTY B'. No real names."
        start_t = time.time()
        with st.spinner("AI Drafting (Keys Rotating)..."):
            res, tank = smart_rotate_draft(p)
            if res:
                st.session_state.final_master = res
                st.session_state.draft_history.insert(0, {"label": f"{dtype} - {datetime.now().strftime('%H:%M')}", "content": res})
                st.success(f"Generated via {tank} in {round(time.time()-start_t, 1)}s")
with b2:
    if st.button("✨ Mirror Style", use_container_width=True, disabled=(selected_ref=="None")):
        doc = Document(os.path.join(VAULT_PATH, selected_ref))
        dna = "\n".join([p.text for p in doc.paragraphs[:12]])
        p = f"Using this Style DNA:\n{dna}\n\nDraft {dtype} for {facts}. Use PARTY A/B."
        with st.spinner(f"Mirroring {selected_ref}..."):
            res, tank = smart_rotate_draft(p)
            if res: st.session_state.final_master = res
with b3:
    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.final_master = ""; st.session_state.facts_input = ""; st.rerun()

# --- 7. THE EDITOR & EXPORT (Req #10, #11, #12, #16) ---
if st.session_state.final_master:
    st.divider()
    # Req #10: Live Party Mapping
    m1, m2 = st.columns(2)
    with m1:
        p_a = st.text_input("Petitioner (PARTY A):")
        if st.button("Map Petitioner"):
            st.session_state.final_master = st.session_state.final_master.replace("PARTY A", p_a); st.rerun()
    with m2:
        p_b = st.text_input("Respondent (PARTY B):")
        if st.button("Map Respondent"):
            st.session_state.final_master = st.session_state.final_master.replace("PARTY B", p_b); st.rerun()

    # Req #11: Editable Text Area
    st.session_state.final_master = st.text_area("Edit Draft:", value=st.session_state.final_master, height=500)
    
    # Req #12 & #16: Export & Cloud
    e1, e2, e3 = st.columns(3)
    with e1:
        if st.button("☁️ Save to Cloud", type="primary", use_container_width=True):
            supabase.table("legal_drafts").insert({"draft type": dtype, "draft content": st.session_state.final_master}).execute()
            st.success("Archived to Supabase!")
    with e2:
        # Word Export
        doc_gen = Document(); doc_gen.add_paragraph(st.session_state.final_master)
        bio = io.BytesIO(); doc_gen.save(bio)
        st.download_button("📥 Word (.docx)", data=bio.getvalue(), file_name=f"{dtype}.docx", use_container_width=True)
    with e3:
        # PDF Export
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=11)
        safe_text = st.session_state.final_master.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 10, safe_text)
        st.download_button("📥 PDF (.pdf)", data=pdf.output(dest='S').encode('latin-1'), file_name=f"{dtype}.pdf", use_container_width=True)
