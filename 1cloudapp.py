import streamlit as st
import time, uuid, pandas as pd
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client
from google import genai

# --- 1. CORE CONFIG & MOBILE POLISH (Points 24, 25, 27, 28) ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

# Initialize Session States
for key, val in {
    "auth": False, "user": "", "master": "", "sid": "",
    "pa_name": "Petitioner", "pb_name": "Respondent", "dna_sample": ""
}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 2. THE KERALA DATASET (Points 1, 3, 22, 23) ---
DISTRICTS = ["Kozhikode", "Thiruvananthapuram", "Ernakulam", "Thrissur", "Kollam", "Palakkad", "Malappuram", "Kannur", "Alappuzha", "Kottayam", "Idukki", "Wayanad", "Pathanamthitta", "Kasaragod"]

COURT_CONFIG = {
    "HIGH COURT": {"dist": ["Ernakulam (High Court)"], "petitions": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Review Petition", "Arb. Request"]},
    "Family Court": {"dist": DISTRICTS, "petitions": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition", "Execution Petition"]},
    "Munsiff Court": {"dist": DISTRICTS, "petitions": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction Application", "Rent Control Petition"]},
    "DISTRICT COURT": {"dist": DISTRICTS, "petitions": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Probate OP", "Motor Accident Claim"]},
    "DVC / MC / MVOP": {"dist": DISTRICTS, "petitions": ["Domestic Violence (DIR)", "Section 125 MC", "MVOP Claim", "Arrear Recovery"]}
}

# --- 3. DATABASE & AI ENGINE (Points 18, 30, 31, 32) ---
@st.cache_resource
def init_db():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except:
        return None

def get_engine():
    # FIXED: Hardened key rotation
    keys = [k[1] for k in st.secrets.get("API_KEYS", []) if len(str(k[1])) > 10]
    m_key = st.secrets.get("GEMINI_KEY")
    f_key = keys[int(time.time()) % len(keys)] if keys else m_key
    return genai.Client(api_key=f_key)

MODEL_MAP = {"Gemini 2.5 Flash": "gemini-2.0-flash", "Gemini 2.5 Pro": "gemini-2.0-pro-exp-02-05"}

# --- 4. LOGIN & KILL SWITCH (Points 17, 26, 34, 35, 39) ---
db = init_db()

if not st.session_state.auth:
    st.title("⚖️ Chamber Terminal Access")
    u_in = st.text_input("User ID").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("Enter Terminal", use_container_width=True):
        creds = st.secrets.get("passwords", {})
        if u_in in creds and str(p_in) == str(creds[u_in]):
            new_sid = str(uuid.uuid4())
            if db:
                try:
                    # FIX: Clear old sessions with a fail-safe
                    db.table("active_sessions").delete().eq("username", u_in).execute()
                    db.table("active_sessions").insert({"username": u_in, "session_id": new_sid}).execute()
                    db.table("login_history").insert({"username": u_in}).execute()
                except: pass # Don't block login if DB write fails
            st.session_state.update({"auth": True, "user": u_in, "sid": new_sid})
            st.rerun()
        else: st.error("Invalid Credentials")
    st.stop()

# Persistent Session Guard
if db:
    try:
        check = db.table("active_sessions").select("session_id").eq("username", st.session_state.user).execute()
        if check.data and check.data[0]['session_id'] != st.session_state.sid:
            st.session_state.auth = False; st.error("🚨 Account logged in elsewhere."); st.rerun()
    except: pass

# --- 5. TOP COMMAND BAR (Point 27) ---
t1, t2 = st.columns([0.8, 0.2])
with t1: st.title(f"⚖️ {st.session_state.user.upper()} WORKSTATION")
with t2:
    if st.button("🚪 Logout", use_container_width=True):
        if db:
            try: db.table("active_sessions").delete().eq("username", st.session_state.user).execute()
            except: pass
        st.session_state.auth = False; st.rerun()

# --- 6. MAIN SELECTORS (Point 38) ---
c1, c2, c3 = st.columns(3)
with c1: sel_court = st.selectbox("Select Court", list(COURT_CONFIG.keys()))
with c2: sel_dist = st.selectbox("District", COURT_CONFIG[sel_court]["dist"])
with c3: sel_pet = st.selectbox("Petition Type", COURT_CONFIG[sel_court]["petitions"])

st.divider()

# --- 7. SIDEBAR: ADMIN & STYLE VAULT (Points 4, 7, 20, 24) ---
with st.sidebar:
    st.header("Terminal Control")
    if st.session_state.user == 'admin':
        sel_model_label = st.selectbox("Engine Suite", list(MODEL_MAP.keys()))
        curr_model = MODEL_MAP[sel_model_label]
        stat_lbl = f"Consulting {sel_model_label}..."
        if st.button("👁️ View Logins"):
            if db:
                logs = db.table("login_history").select("*").order("id", desc=True).limit(5).execute()
                for l in logs.data: st.caption(f"👤 {l['username']} | {l['created_at'][11:16]}")
    else:
        st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)
        curr_model = "gemini-2.0-flash"; stat_lbl = "AI Drafting Case..."
        st.info("🚀 AI System: Active")

    st.divider(); st.subheader("📂 STYLE VAULT")
    if db:
        try:
            hist = db.table("legal_drafts").select("*").eq("username", st.session_state.user).order("id", desc=True).limit(10).execute()
            for item in hist.data:
                if st.button(f"📄 {item['type'][:12]}...", key=f"h_{item['id']}"):
                    st.session_state.master = item['content']
                    st.session_state.dna_sample = item['content']
                    st.success("Style Reference Loaded!")
        except: st.caption("Vault empty.")

# --- 8. WORKSTATION (Points 5-11, 13) ---
w1, w2 = st.columns(2)
with w1:
    st.subheader("Case DNA")
    pr1, pr2 = st.columns([0.8, 0.2])
    pa = pr1.text_input("PARTY A", value=st.session_state.pa_name)
    if pr2.button("⇄"):
        st.session_state.pa_name, st.session_state.pb_name = st.session_state.pb_name, st.session_state.pa_name
        st.rerun()
    pb = st.text_input("PARTY B", value=st.session_state.pb_name)
    
    st.markdown(f"🔗 [Precedents: Indian Kanoon](https://indiankanoon.org/search/?formInput={sel_pet}+kerala)")
    facts = st.text_area("Case Facts", height=200)
    
    if st.button("🚀 AI Draft", type="primary", use_container_width=True):
        with st.status(stat_lbl) as s:
            t0 = time.time()
            try:
                # Mirror Logic + Strict Party Mapping
                dna = f"Mirror this style: {st.session_state.dna_sample[:600]}" if st.session_state.dna_sample else ""
                prompt = f"Draft {sel_pet} for {sel_court} in {sel_dist}. PARTY A: {pa}, PARTY B: {pb}. {dna}. Facts: {facts}"
                res = get_engine().models.generate_content(model=curr_model, contents=prompt)
                st.session_state.master = res.text
                s.update(label=f"Done in {round(time.time()-t0, 1)}s", state="complete")
                st.rerun()
            except Exception as e: st.error(f"AI Service Busy: {str(e)[:50]}")

with w2:
    st.subheader("Live Editor")
    with st.expander("🔍 Search and Replace"):
        f_w = st.text_input("Find"); r_w = st.text_input("Replace")
        if st.button("Apply"): st.session_state.master = st.session_state.master.replace(f_w, r_w); st.rerun()
            
    st.session_state.master = st.text_area("Editor", value=st.session_state.master, height=450)

# --- 9. EXPORTS & RESET (Points 12, 14, 16, 19) ---
st.divider()
e1, e2, e3, e4 = st.columns(4)
with e1:
    if st.button("☁️ Cloud Save", disabled=(st.session_state.user != 'admin'), use_container_width=True):
        if db:
            try:
                db.table("legal_drafts").insert({"username": st.session_state.user, "content": st.session_state.master, "type": sel_pet}).execute()
                st.success("Saved.")
            except: st.error("Save failed.")
with e2:
    doc = Document(); doc.add_paragraph(st.session_state.master); bio = BytesIO(); doc.save(bio)
    st.download_button("📝 DOCX Export", bio.getvalue(), "draft.docx", use_container_width=True)
with e3:
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12); pdf.multi_cell(0, 10, st.session_state.master)
    st.download_button("📄 PDF Export", pdf.output(dest='S'), "draft.pdf", use_container_width=True)
with e4:
    if st.button("♻️ Reset Workspace", use_container_width=True):
        st.session_state.master = ""; st.session_state.pa_name = "Petitioner"; st.session_state.pb_name = "Respondent"; st.rerun()
