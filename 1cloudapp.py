import streamlit as st
import os, io, urllib.parse, time
from datetime import datetime
from google import genai
from docx import Document
from fpdf import FPDF
from supabase import create_client, Client

# --- 1. CONFIG & AUTH STATE (Req #17) ---
st.set_page_config(page_title="Senior Advocate Workstation", layout="wide")

DEFAULTS = {
    "authenticated": False, "user_role": None, "final_master": "", 
    "draft_history": [], "facts_input": "", "selected_model": "Auto-Pilot"
}
for key, val in DEFAULTS.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 2. CLOUD & STORAGE (Req #16, #17) ---
SUPABASE_URL = "https://wuhsjcwtoradbzeqsoih.supabase.co"
SUPABASE_KEY = "sb_publishable_02nqexIYCCBaWryubZEkqA_Tw2PqX6m"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
VAULT_PATH = "private_vault"
if not os.path.exists(VAULT_PATH): os.makedirs(VAULT_PATH)

# --- 3. DYNAMIC PETITION DATA (Req #3, #4) ---
COURT_DATA = {
    "High Court": ["Writ Petition (Civil)", "Writ Petition (Crl)", "Bail App", "Crl.MC", "Mat.Appeal", "RFA", "RSA"],
    "Family Court": ["OP (Divorce)", "MC (Maintenance)", "GOP (Guardianship)", "OP (Restitution)", "IA (Interim)"],
    "Munsiff Court": ["OS (Original Suit)", "EP (Execution Petition)", "RCP (Rent Control)", "CMA (Misc Appeal)"],
    "DVC (Domestic Violence)": ["DVA (Protection Order)", "Interim Maintenance", "Residence Order"],
    "MC (Magistrate)": ["CMP (Misc Petition)", "ST (Summary Trial)", "CC (Calendar Case)", "Bail Application"],
    "MVOP (Motor Accident)": ["OP (MV) Claim", "Ex-parte Set Aside", "Review Petition"]
}

# --- 4. SMART ENGINE (Req #14, #18, #19, #20) ---
def smart_rotate_draft(prompt, facts, choice):
    projects = st.secrets.get("API_KEYS", [])
    # Req #20: Manual vs Automatic
    if choice == "Auto-Pilot":
        target_model = "gemini-2.5-pro" if len(facts) > 1200 else "gemini-2.5-flash"
    else:
        target_model = choice

    start_time = time.time() # Req #14: Timer Start
    for name, key in projects:
        try:
            client = genai.Client(api_key=key)
            res = client.models.generate_content(model=target_model, contents=prompt)
            elapsed = round(time.time() - start_time, 1)
            return res.text, f"{name} ({target_model})", elapsed
        except Exception as e:
            if "429" in str(e): continue
            return None, f"Error: {str(e)}", 0

    # Emergency Fallback to Lite (1,000 RPD)
    for name, key in projects:
        try:
            client = genai.Client(api_key=key)
            res = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
            elapsed = round(time.time() - start_time, 1)
            return res.text, f"{name} (LITE-FAILOVER)", elapsed
        except: continue
    return None, "All quotas exhausted.", 0

# --- 5. LOGIN (Req #18) ---
if not st.session_state.authenticated:
    st.title("👨‍⚖️ Workstation Login")
    with st.form("login"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Access"):
            creds = st.secrets.get("passwords", {})
            if u in creds and p == creds[u]:
                st.session_state.authenticated = True; st.session_state.user_role = u; st.rerun()
    st.stop()

# --- 6. SIDEBAR (Req #6, #18, #20) ---
with st.sidebar:
    st.header(f"Adv. {st.session_state.user_role.upper()}")
    if st.button("🚪 Logout"): st.session_state.authenticated = False; st.rerun()
    
    st.divider()
    st.subheader("📜 History (Last 10)")
    for i, item in enumerate(st.session_state.draft_history[:10]):
        if st.button(item["label"], key=f"h_{i}", use_container_width=True):
            st.session_state.final_master = item["content"]; st.rerun()

    st.divider()
    st.session_state.selected_model = st.radio("Intelligence Mode:", ["Auto-Pilot", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"])
    
    st.divider()
    uploaded = st.file_uploader("Vault Reference (.docx)", type="docx")
    if uploaded:
        with open(os.path.join(VAULT_PATH, uploaded.name), "wb") as f: f.write(uploaded.getbuffer())
    selected_ref = st.selectbox("Mirror Logic:", ["None"] + os.listdir(VAULT_PATH))

# --- 7. MAIN INTERFACE ---
st.title("Legal Drafting Terminal")
c1, c2 = st.columns(2)
with c1:
    court = st.selectbox("Court Level", list(COURT_DATA.keys())) # Req #3
    dtype = st.selectbox("Petition Type", COURT_DATA[court]) # Req #4
with c2:
    dists = ["Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad", "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod"]
    target_dist = "Ernakulam" if court == "High Court" else st.selectbox("District", dists) # Req #5

st.session_state.facts_input = st.text_area("Case Facts:", value=st.session_state.facts_input, height=150)

# Req #7 & #8: Research
if st.session_state.facts_input:
    search_q = urllib.parse.quote(f"{dtype} {st.session_state.facts_input[:50]} Kerala")
    with st.expander("🔍 Precedents & Indian Kanoon Research"):
        st.markdown(f"🔗 [Direct Research Link for {dtype}](https://indiankanoon.org/search/?formInput={search_q})")
        st.info("API Search Container: Analyzing facts for relevant CrPC/BNSS sections...")

b1, b2, b3 = st.columns(3)
with b1:
    if st.button("🚀 Draft Standard", type="primary", use_container_width=True):
        p = f"Draft {dtype} for {court} at {target_dist}. Facts: {st.session_state.facts_input}. STRICTLY USE PARTY A/B. NO REAL NAMES."
        with st.spinner("AI Drafting..."):
            res, tank, sec = smart_rotate_draft(p, st.session_state.facts_input, st.session_state.selected_model)
            if res:
                st.session_state.final_master = res
                st.session_state.draft_history.insert(0, {"label": f"{dtype} ({datetime.now().strftime('%H:%M')})", "content": res})
                st.toast(f"Generated in {sec}s via {tank}")
with b2:
    if st.button("✨ Mirror Style", use_container_width=True, disabled=(selected_ref=="None")):
        doc = Document(os.path.join(VAULT_PATH, selected_ref))
        dna = "\n".join([p.text for p in doc.paragraphs[:15]])
        p = f"Using this STYLE DNA:\n{dna}\n\nDraft {dtype} for {st.session_state.facts_input}. Use PARTY A/B."
        with st.spinner("Mirroring..."):
            res, tank, sec = smart_rotate_draft(p, st.session_state.facts_input, st.session_state.selected_model)
            if res: st.session_state.final_master = res
with b3:
    if st.button("🗑️ Reset All", use_container_width=True): # Req #15
        st.session_state.final_master = ""; st.session_state.facts_input = ""; st.rerun()

# --- 8. EDITOR & MAPPING (Req #10, #11, #12, #13) ---
if st.session_state.final_master:
    st.divider()
    m1, m2 = st.columns(2)
    with m1:
        p_a = st.text_input("Petitioner (PARTY A):")
        if st.button("Map A"): st.session_state.final_master = st.session_state.final_master.replace("PARTY A", p_a); st.rerun()
    with m2:
        p_b = st.text_input("Respondent (PARTY B):")
        if st.button("Map B"): st.session_state.final_master = st.session_state.final_master.replace("PARTY B", p_b); st.rerun()

    st.session_state.final_master = st.text_area("Workstation Editor", value=st.session_state.final_master, height=500)
    
    e1, e2, e3 = st.columns(3)
    with e1:
        if st.button("☁️ Cloud Save", type="primary", use_container_width=True):
            supabase.table("legal_drafts").insert({"type": dtype, "content": st.session_state.final_master}).execute()
            st.success("Saved to Supabase")
    with e2:
        doc_gen = Document(); doc_gen.add_paragraph(st.session_state.final_master)
        bio = io.BytesIO(); doc_gen.save(bio)
        st.download_button("📥 MS Word", data=bio.getvalue(), file_name=f"{dtype}.docx", use_container_width=True)
    with e3:
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 10, st.session_state.final_master.encode('latin-1', 'replace').decode('latin-1'))
        st.download_button("📥 PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"{dtype}.pdf", use_container_width=True)
