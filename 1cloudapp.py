import streamlit as st
import os, io, urllib.parse, time
from datetime import datetime
from google import genai
from docx import Document
from fpdf import FPDF
from supabase import create_client, Client

# --- 1. CONFIG & AUTH STATE ---
st.set_page_config(page_title="Senior Advocate Workstation", layout="wide")

DEFAULTS = {
    "authenticated": False, "user_role": None, "final_master": "", 
    "draft_history": [], "facts_input": "", "selected_model": "Auto-Pilot"
}
for key, val in DEFAULTS.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 2. CLOUD & STORAGE ---
SUPABASE_URL = "https://wuhsjcwtoradbzeqsoih.supabase.co"
SUPABASE_KEY = "sb_publishable_02nqexIYCCBaWryubZEkqA_Tw2PqX6m"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
VAULT_PATH = "private_vault"
if not os.path.exists(VAULT_PATH): os.makedirs(VAULT_PATH)

# --- 3. DATA & UTILITIES ---
COURT_DATA = {
    "High Court": ["Writ Petition (Civil)", "Writ Petition (Crl)", "Bail App", "Crl.MC", "Mat.Appeal", "RFA", "RSA"],
    "Family Court": ["OP (Divorce)", "MC (Maintenance)", "GOP (Guardianship)", "OP (Restitution)", "IA (Interim)"],
    "Munsiff Court": ["OS (Original Suit)", "EP (Execution Petition)", "RCP (Rent Control)", "CMA (Misc Appeal)"],
    "DVC (Domestic Violence)": ["DVA (Protection Order)", "Interim Maintenance", "Residence Order"],
    "MC (Magistrate)": ["CMP (Misc Petition)", "ST (Summary Trial)", "CC (Calendar Case)", "Bail Application"],
    "MVOP (Motor Accident)": ["OP (MV) Claim", "Ex-parte Set Aside", "Review Petition"]
}

def map_text(old, new):
    if new: st.session_state.final_master = st.session_state.final_master.replace(old, new)

# --- 4. ENGINE: SMART ROTATION ---
def smart_rotate_draft(prompt, facts, choice):
    projects = st.secrets.get("API_KEYS", [])
    # If user is not admin, choice is forced to Auto-Pilot
    effective_choice = choice if st.session_state.user_role == "admin" else "Auto-Pilot"
    
    target_model = effective_choice if effective_choice != "Auto-Pilot" else ("gemini-2.5-pro" if len(facts) > 1200 else "gemini-2.5-flash")
    start_time = time.time()
    
    for name, key in projects:
        try:
            client = genai.Client(api_key=key)
            res = client.models.generate_content(model=target_model, contents=prompt)
            return res.text, f"{name} ({target_model})", round(time.time() - start_time, 1)
        except Exception as e:
            if "429" in str(e): continue
            return None, f"Error: {str(e)}", 0

    for name, key in projects:
        try:
            client = genai.Client(api_key=key)
            res = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
            return res.text, f"{name} (FAILOVER-LITE)", round(time.time() - start_time, 1)
        except: continue
    return None, "All quotas exhausted.", 0

# --- 5. LOGIN ---
if not st.session_state.authenticated:
    st.title("👨‍⚖️ Workstation Login")
    with st.form("login"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Access"):
            creds = st.secrets.get("passwords", {})
            if u in creds and p == creds[u]:
                st.session_state.authenticated = True; st.session_state.user_role = u.lower(); st.rerun()
    st.stop()

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header(f"Adv. {st.session_state.user_role.upper()}")
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.rerun()
    st.divider()
    st.subheader("📜 History (Last 10)")
    for i, item in enumerate(st.session_state.draft_history[:10]):
        if st.button(item["label"], key=f"h_{i}", use_container_width=True):
            st.session_state.final_master = item["content"]; st.rerun()
    
    # Req: Model selection ONLY for Admin
    if st.session_state.user_role == "admin":
        st.divider()
        st.session_state.selected_model = st.radio("Intelligence Mode:", ["Auto-Pilot", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"])
    else:
        st.session_state.selected_model = "Auto-Pilot"

    st.divider()
    uploaded = st.file_uploader("Vault Reference (.docx)", type="docx")
    if uploaded:
        with open(os.path.join(VAULT_PATH, uploaded.name), "wb") as f: f.write(uploaded.getbuffer())
    selected_ref = st.selectbox("Mirror Logic:", ["None"] + os.listdir(VAULT_PATH))

# --- 7. MAIN INTERFACE ---
st.title("Legal Drafting Terminal")
c1, c2 = st.columns(2)
with c1:
    court = st.selectbox("Court Level", list(COURT_DATA.keys()))
    dtype = st.selectbox("Petition Type", COURT_DATA[court])
with c2:
    dists = ["Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad", "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod"]
    target_dist = "Ernakulam" if court == "High Court" else st.selectbox("District", dists)

st.session_state.facts_input = st.text_area("Case Facts:", value=st.session_state.facts_input, height=150)

if st.session_state.facts_input:
    search_q = urllib.parse.quote(f"{dtype} {st.session_state.facts_input[:50]} Kerala")
    with st.expander("🔍 Precedents & Indian Kanoon Research", expanded=True):
        st.markdown(f"🔗 [Direct Research Link for {dtype}](https://indiankanoon.org/search/?formInput={search_q})")
        st.info(f"Kanoon API Container: Recommended statutes for {dtype} found.")

b1, b2, b3 = st.columns(3)
with b1:
    if st.button("🚀 Draft Standard", type="primary", use_container_width=True):
        p = f"Draft {dtype} for {court} at {target_dist}. Facts: {st.session_state.facts_input}. STRICTLY USE PARTY A/B. NO REAL NAMES."
        with st.spinner("AI Drafting..."):
            res, tank, sec = smart_rotate_draft(p, st.session_state.facts_input, st.session_state.selected_model)
            if res:
                st.session_state.final_master = res
                st.session_state.draft_history.insert(0, {"label": f"{dtype} ({datetime.now().strftime('%H:%M')})", "content": res})
                # Show source only to admin
                msg = f"Generated in {sec}s" + (f" via {tank}" if st.session_state.user_role == "admin" else "")
                st.toast(msg)
with b2:
    if st.button("✨ Mirror Style", use_container_width=True, disabled=(selected_ref=="None")):
        doc = Document(os.path.join(VAULT_PATH, selected_ref))
        dna = "\n".join([p.text for p in doc.paragraphs[:15]])
        p = f"Using this STYLE DNA:\n{dna}\n\nDraft {dtype} for {st.session_state.facts_input}. Use PARTY A/B."
        with st.spinner("Mirroring..."):
            res, tank, sec = smart_rotate_draft(p, st.session_state.facts_input, st.session_state.selected_model)
            if res: st.session_state.final_master = res
with b3:
    if st.button("🗑️ Reset All", use_container_width=True):
        st.session_state.final_master = ""; st.session_state.facts_input = ""; st.rerun()

# --- 8. EDITOR & MAPPING ---
if st.session_state.final_master:
    st.divider()
    st.subheader("📝 Draft Customization")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        p_a = st.text_input("Petitioner Name:")
        st.button("Replace 'PARTY A'", on_click=map_text, args=("PARTY A", p_a), use_container_width=True)
    with col_b:
        p_b = st.text_input("Respondent Name:")
        st.button("Replace 'PARTY B'", on_click=map_text, args=("PARTY B", p_b), use_container_width=True)
    with col_c:
        f_old = st.text_input("Find:")
        f_new = st.text_input("Replace with:")
        st.button("Custom Replace", on_click=map_text, args=(f_old, f_new), use_container_width=True)

    st.session_state.final_master = st.text_area("Live Workstation Editor", value=st.session_state.final_master, height=500, key="main_editor")
    
    e1, e2, e3 = st.columns(3)
    with e1:
        # Req: Cloud Save only for Admin
        is_admin = st.session_state.user_role == "admin"
        if st.button("☁️ Cloud Save", type="primary", use_container_width=True, disabled=not is_admin, help="Admin Only Feature" if not is_admin else None):
            supabase.table("legal_drafts").insert({"type": dtype, "content": st.session_state.final_master}).execute()
            st.success("Saved to Cloud")
    with e2:
        doc_gen = Document(); doc_gen.add_paragraph(st.session_state.final_master)
        bio = io.BytesIO(); doc_gen.save(bio)
        st.download_button("📥 MS Word", data=bio.getvalue(), file_name=f"{dtype}.docx", use_container_width=True)
    with e3:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 10, st.session_state.final_master.encode('latin-1', 'replace').decode('latin-1'))
        st.download_button("📥 PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"{dtype}.pdf", use_container_width=True)
