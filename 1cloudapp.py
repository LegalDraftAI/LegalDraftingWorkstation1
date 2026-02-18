import streamlit as st
import time, uuid
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client
from google import genai

# --- 1. CORE CONFIG (Point 24, 25, 28) ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

# Persistent Session Logic
if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""
if 'master' not in st.session_state: st.session_state.master = ""

def apply_ui_security():
    # Point 24: Hide headers/footers for non-admins (Clean UI)
    if st.session_state.user != 'admin':
        st.markdown("""<style>
            #MainMenu, footer, header {visibility: hidden;}
            .stDeployButton {display:none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            </style>""", unsafe_allow_html=True)

# --- 2. DATABASE & ROTATION (Point 31) ---
@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def get_engine():
    # Smart rotation across keys to prevent rate limits
    raw_keys = st.secrets.get("API_KEYS", [])
    valid_keys = [k[1] for k in raw_keys if len(k) > 1]
    if not valid_keys: return genai.Client(api_key=st.secrets.get("GEMINI_KEY", "dummy"))
    idx = int(time.time()) % len(valid_keys)
    return genai.Client(api_key=valid_keys[idx])

COURTS = {
    "HIGH COURT": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Review Petition"],
    "Family Court": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition"],
    "Munsiff Court": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction Application"],
    "DISTRICT COURT": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Motor Accident Claim"],
    "DVC/MC/MVOP": ["DVC (Domestic Violence)", "MC (Maintenance Case)", "MVOP (Motor Accident)"]
}

# --- 3. LOGIN GATE ---
if not st.session_state.auth:
    st.title("⚖️ Chamber Terminal Access")
    u_in = st.text_input("User ID").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("Enter Terminal", use_container_width=True):
        creds = st.secrets.get("passwords", {})
        if u_in in creds and str(p_in) == str(creds[u_in]):
            st.session_state.update({"auth": True, "user": u_in, "sid": str(uuid.uuid4())})
            try:
                init_db().table("login_history").insert({"username": u_in}).execute()
            except: pass # Silent fail if DB is busy
            st.rerun()
    st.stop()

apply_ui_security()

# --- 4. TOP NAVIGATION (Visible & Reliable) ---
t_col1, t_col2 = st.columns([0.8, 0.2])
with t_col1:
    st.subheader(f"👤 {st.session_state.user.upper()} | Chamber Terminal")
with t_col2:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- 5. MAIN INTERFACE SELECTORS (Point 38 - Outside Sidebar) ---
st.markdown("---")
c1, c2, c3 = st.columns(3)
with c1:
    sel_court = st.selectbox("Select Court", list(COURTS.keys()))
with c2:
    if sel_court == "HIGH COURT":
        sel_dist = st.selectbox("District", ["Ernakulam (High Court)"], disabled=True)
    else:
        sel_dist = st.selectbox("District", ["Kozhikode", "Tvm", "Thrissur", "Kollam", "Palakkad"])
with c3:
    sel_pet = st.selectbox("Petition Type", COURTS[sel_court])

# --- 6. SIDEBAR: ADMIN & VAULT ONLY ---
with st.sidebar:
    st.header("Admin Controls")
    if st.session_state.user == 'admin':
        # Point 30: Explicit Gemini 2.5 Models
        sel_model = st.selectbox("Engine Suite", ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"])
        if st.button("👁️ Audit Logins"):
            try:
                logs = init_db().table("login_history").select("*").order("id", desc=True).limit(5).execute()
                for l in logs.data: st.caption(f"👤 {l['username']}")
            except: st.error("Log access failed")
    else:
        sel_model = "gemini-2.5-flash"
        st.info("🚀 AI Optimizer: Active")
    
    st.divider()
    st.subheader("Last 10 Cases")
    try:
        hist = init_db().table("legal_drafts").select("*").eq("username", st.session_state.user).order("id", desc=True).limit(10).execute()
        for item in hist.data:
            if st.button(f"📅 {item['created_at'][5:10]} | {item['type'][:10]}", key=f"h_{item['id']}"):
                st.session_state.master = item['content']
                st.rerun()
    except:
        st.caption("No history in Vault.")

# --- 7. WORKSTATION ---
w1, w2 = st.columns(2)
with w1:
    st.subheader("Case Details")
    pa = st.text_input("PARTY A", value="Petitioner")
    pb = st.text_input("PARTY B", value="Respondent")
    facts = st.text_area("Facts & Grounds", height=250)
    
    if st.button("🚀 AI Draft", type="primary", use_container_width=True):
        with st.status(f"Consulting {sel_model}...") as s:
            t_start = time.time()
            client = get_engine()
            res = client.models.generate_content(model=sel_model, contents=f"Draft {sel_pet} for {pa} vs {pb}. Facts: {facts}")
            st.session_state.master = res.text
            s.update(label=f"Done in {round(time.time()-t_start, 1)}s", state="complete")

with w2:
    st.subheader("Live Editor")
    st.session_state.master = st.text_area("Editor", value=st.session_state.master, height=450)

# --- 8. EXPORTS (Point 19) ---
st.divider()
e1, e2, e3, e4 = st.columns(4)
with e1:
    can_save = (st.session_state.user == 'admin')
    if st.button("☁️ Cloud Save", disabled=not can_save, use_container_width=True):
        try:
            init_db().table("legal_drafts").insert({"username": st.session_state.user, "content": st.session_state.master, "type": sel_pet}).execute()
            st.success("Draft Saved.")
        except: st.error("Save failed.")
with e2:
    doc = Document(); doc.add_paragraph(st.session_state.master); bio = BytesIO(); doc.save(bio)
    st.download_button("📝 DOCX", bio.getvalue(), "draft.docx", use_container_width=True)
with e3:
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12); pdf.multi_cell(0, 10, st.session_state.master)
    st.download_button("📄 PDF", pdf.output(dest='S'), "draft.pdf", use_container_width=True)
with e4:
    if st.button("♻️ Clear", use_container_width=True):
        st.session_state.master = ""; st.rerun()
