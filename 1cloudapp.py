import streamlit as st
import time, uuid, pandas as pd
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client
from google import genai

# --- 1. CORE CONFIG & MOBILE POLISH (Points 24, 25, 27, 28, 37) ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""
if 'master' not in st.session_state: st.session_state.master = ""
if 'pa_name' not in st.session_state: st.session_state.pa_name = "Petitioner"
if 'pb_name' not in st.session_state: st.session_state.pb_name = "Respondent"

# --- 2. DATA VAULT: ALL KERALA COURTS & PETITIONS (Points 1, 2, 22, 23) ---
DISTRICTS = ["Kozhikode", "Thiruvananthapuram", "Ernakulam", "Thrissur", "Kollam", "Palakkad", "Malappuram", "Kannur", "Alappuzha", "Kottayam", "Idukki", "Wayanad", "Pathanamthitta", "Kasaragod"]

COURT_CONFIG = {
    "HIGH COURT": {
        "districts": ["Ernakulam (High Court)"], # Point 3: HC Auto-Lock
        "petitions": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Matrimonial Appeal", "Review Petition", "Arbitration Request"]
    },
    "Family Court": {
        "districts": DISTRICTS,
        "petitions": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition", "Execution Petition"]
    },
    "Munsiff Court": {
        "districts": DISTRICTS,
        "petitions": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction Application", "Rent Control Petition"]
    },
    "DISTRICT COURT": {
        "districts": DISTRICTS,
        "petitions": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Probate OP", "Motor Accident Claim"]
    },
    "DVC / MC / MVOP": {
        "districts": DISTRICTS,
        "petitions": ["Domestic Violence (DIR)", "Section 125 MC", "MVOP Claim", "Arrear Recovery"]
    }
}

# --- 3. DATABASE & AI ROTATION (Points 18, 29, 31, 32, 37) ---
@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def get_engine():
    raw_keys = st.secrets.get("API_KEYS", [])
    valid_keys = [k[1] for k in raw_keys if len(k) > 1]
    # Point 31: Smart Round-Robin Rotation
    idx = int(time.time()) % len(valid_keys) if valid_keys else 0
    return genai.Client(api_key=valid_keys[idx] if valid_keys else st.secrets["GEMINI_KEY"])

# --- 4. AUTH & KILL SWITCH & LOGGING (Points 17, 21, 26, 34, 35, 39) ---
if not st.session_state.auth:
    st.title("⚖️ Chamber Terminal Access")
    u_in = st.text_input("User ID").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("Enter Terminal", use_container_width=True):
        creds = st.secrets.get("passwords", {})
        if u_in in creds and str(p_in) == str(creds[u_in]):
            sid = str(uuid.uuid4())
            try:
                # Point 34/26/39: Kill Switch & Logging
                init_db().table("active_sessions").upsert({"username": u_in, "session_id": sid}).execute()
                init_db().table("login_history").insert({"username": u_in}).execute()
            except: pass
            st.session_state.update({"auth": True, "user": u_in, "sid": sid})
            st.rerun()
    st.stop()

# Kill Switch Check
try:
    check = init_db().table("active_sessions").select("session_id").eq("username", st.session_state.user).execute()
    if check.data and check.data[0]['session_id'] != st.session_state.sid:
        st.session_state.auth = False; st.error("🚨 Session Logged in Elsewhere"); time.sleep(2); st.rerun()
except: pass

# --- 5. THE COMMAND BAR (Point 27) ---
c_nav1, c_nav2 = st.columns([0.8, 0.2])
with c_nav1:
    st.title(f"⚖️ {st.session_state.user.upper()} WORKSTATION")
with c_nav2:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth = False; st.rerun()

# --- 6. MAIN INTERFACE SELECTORS (Point 38) ---
c_sel1, c_sel2, c_sel3 = st.columns(3)
with c_sel1:
    sel_court = st.selectbox("Court", list(COURT_CONFIG.keys()))
with c_sel2:
    sel_dist = st.selectbox("District", COURT_CONFIG[sel_court]["districts"])
with c_sel3:
    sel_pet = st.selectbox("Petition Type", COURT_CONFIG[sel_court]["petitions"])

st.divider()

# --- 7. SIDEBAR: ADMIN & VAULT (Points 4, 15, 20, 21, 24, 25, 30, 36) ---
with st.sidebar:
    st.header("Terminal Control")
    if st.session_state.user == 'admin':
        # Point 20/30: Admin-only Model Selection
        sel_model = st.selectbox("Engine Suite", ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"])
        if st.button("👁️ View Logins"):
            logs = init_db().table("login_history").select("*").order("id", desc=True).limit(5).execute()
            for l in logs.data: st.caption(f"👤 {l['username']} | {l['created_at'][11:16]}")
        if st.button("📥 Download History CSV"): # Point 21
            logs = init_db().table("login_history").select("*").execute()
            st.download_button("Download CSV", pd.DataFrame(logs.data).to_csv().encode('utf-8'), "history.csv")
    else:
        # Point 24: Hide dev tools for Juniors/Seniors
        st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)
        sel_model = "gemini-2.5-flash" # Point 20 Auto-Pilot
        st.info("🚀 AI Running: Optimized Flash")

    st.divider()
    st.subheader("Last 10 Cases (Vault)") # Point 4/15
    try:
        hist = init_db().table("legal_drafts").select("*").eq("username", st.session_state.user).order("id", desc=True).limit(10).execute()
        for item in hist.data:
            if st.button(f"📄 {item['type'][:15]}...", key=f"h_{item['id']}"):
                st.session_state.master = item['content']; st.rerun()
    except: st.caption("Vault empty.")

# --- 8. WORKSTATION: DRAFTING (Points 6, 7, 8, 9, 11, 13) ---
w_col1, w_col2 = st.columns(2)
with w_col1:
    st.subheader("Case DNA")
    # Point 9: Live Party Mapping & Swap
    p_row1, p_row2 = st.columns([0.8, 0.2])
    pa = p_row1.text_input("PARTY A", value=st.session_state.pa_name)
    if p_row2.button("⇄", help="Swap Parties"):
        st.session_state.pa_name, st.session_state.pb_name = st.session_state.pb_name, st.session_state.pa_name
        st.rerun()
    pb = st.text_input("PARTY B", value=st.session_state.pb_name)
    
    st.markdown(f"🔗 [Research Precedents on Indian Kanoon](https://indiankanoon.org/search/?formInput={sel_pet}+kerala)") # Point 6
    facts = st.text_area("Case Facts (Mirror Style DNA)", height=250) # Point 7
    
    if st.button("🚀 AI Draft", type="primary", use_container_width=True):
        with st.status(f"Consulting {sel_model}...") as s: # Point 13: Timer
            t_start = time.time()
            # Point 8: Strict "PARTY A/B" AI Logic
            prompt = f"Draft a formal {sel_pet} for {sel_court} in {sel_dist}. Use labels 'PARTY A' for {pa} and 'PARTY B' for {pb}. Facts: {facts}"
            res = get_engine().models.generate_content(model=sel_model, contents=prompt)
            st.session_state.master = res.text
            s.update(label=f"Completed in {round(time.time()-t_start, 1)}s", state="complete")
            st.rerun()

with w_col2:
    st.subheader("Live Editor")
    # Point 10: Search and Replace Function
    with st.expander("🔍 Search and Replace"):
        f_find = st.text_input("Find Word")
        f_repl = st.text_input("Replace With")
        if st.button("Apply Globally"):
            st.session_state.master = st.session_state.master.replace(f_find, f_repl)
            st.rerun()
            
    # Point 11: Editable Workstation
    st.session_state.master = st.text_area("Editor", value=st.session_state.master, height=450)

# --- 9. EXPORTS & CLOUD (Points 12, 14, 16, 19) ---
st.divider()
e1, e2, e3, e4 = st.columns(4)
with e1:
    # Point 19: Only Admin Cloud Save
    if st.button("☁️ Cloud Save", disabled=(st.session_state.user != 'admin'), use_container_width=True):
        try:
            init_db().table("legal_drafts").insert({"username": st.session_state.user, "content": st.session_state.master, "type": sel_pet}).execute()
            st.success("Saved to Vault.")
        except: st.error("Save failed.")
with e2:
    doc = Document(); doc.add_paragraph(st.session_state.master); bio = BytesIO(); doc.save(bio)
    st.download_button("📝 DOCX Export", bio.getvalue(), "draft.docx", use_container_width=True) # Point 12
with e3:
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12); pdf.multi_cell(0, 10, st.session_state.master)
    st.download_button("📄 PDF Export", pdf.output(dest='S'), "draft.pdf", use_container_width=True) # Point 12
with e4:
    if st.button("♻️ Reset Workspace", use_container_width=True): # Point 14
        st.session_state.master = ""; st.rerun()
