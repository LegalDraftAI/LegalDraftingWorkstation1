import streamlit as st
import time, uuid, pandas as pd
from datetime import datetime
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client, Client
from google import genai

# --- 1. CORE UI & SECURITY CONFIG (Points 24, 25, 27, 28) ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

def apply_ui_security(role):
    if role != 'admin':
        # Point 24: Hide all developer tools, icons, and menus for Juniors/Seniors
        st.markdown("""<style>
            #MainMenu, footer, header {visibility: hidden;}
            .stDeployButton {display:none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            </style>""", unsafe_allow_html=True)

# --- 2. DATABASE & ROTATION ENGINE (Points 18, 29, 31, 32, 37) ---
@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def get_engine():
    # Point 18 & 31: 5-Key Smart Rotation
    raw_keys = st.secrets.get("API_KEYS", [])
    valid_keys = [k[1] for k in raw_keys if k[1] and len(k[1]) > 10]
    if not valid_keys: st.error("No API Keys Found"); st.stop()
    idx = int(time.time()) % len(valid_keys)
    return genai.Client(api_key=valid_keys[idx])

# --- 3. EXPANDED KERALA COURT DATA (Points 1, 2, 22, 23) ---
COURTS = {
    "HIGH COURT": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Matrimonial Appeal", "Review Petition", "Arbitration Request"],
    "Family Court": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition", "Execution Petition"],
    "Munsiff Court": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction Application", "Rent Control Petition"],
    "DISTRICT COURT": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Probate OP", "Motor Accident Claim"],
    "DVC": ["Domestic Violence Complaint (DIR)", "Interim Relief Application", "Monetary Relief"],
    "MC": ["Section 125 Maintenance Case", "Arrear Recovery", "Modification of Order"],
    "MVOP": ["Claim for Compensation", "Interim Award Application", "Third Party Insurance Claim"]
}

# --- 4. AUTH & DUAL-TABLE SECURITY (Points 17, 21, 26, 34, 35) ---
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("⚖️ Chamber Terminal Access")
    u_in = st.text_input("User ID").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("Enter Terminal", use_container_width=True):
        creds = st.secrets.get("passwords", {})
        if u_in in creds and p_in == creds[u_in]:
            sid = str(uuid.uuid4())
            # Point 34/26: Kill Switch Activation
            sb.table("active_sessions").upsert({"username": u_in, "session_id": sid}).execute()
            # Point 35/21: Login History Log
            sb.table("login_history").insert({"username": u_in, "session_id": sid}).execute()
            st.session_state.update({"auth":True, "user":u_in, "sid":sid, "master":"", "pa_name":"Petitioner", "pb_name":"Respondent"})
            st.rerun()
    st.stop()

# Continuous Kill Switch Guard
check = sb.table("active_sessions").select("session_id").eq("username", st.session_state.user).execute()
if check.data and check.data[0]['session_id'] != st.session_state.sid:
    st.error("🚨 Access Revoked: Account active elsewhere."); st.session_state.auth = False; time.sleep(2); st.rerun()

apply_ui_security(st.session_state.user)

# --- 5. COMMAND BAR (Point 27) ---
c1, c2 = st.columns([0.85, 0.15])
c1.title(f"⚖️ {st.session_state.user.upper()} WORKSTATION")
if c2.button("🚪 Logout", use_container_width=True):
    sb.table("active_sessions").delete().eq("username", st.session_state.user).execute()
    st.session_state.auth = False; st.rerun()

# --- 6. MAIN INTERFACE SELECTORS (Point 38, 3, 22, 23) ---
c_top1, c_top2, c_top3 = st.columns(3)
with c_top1:
    sel_court = st.selectbox("Select Court", list(COURTS.keys()))
with c_top2:
    # Point 3: HC Ernakulam Auto-Lock
    if sel_court == "HIGH COURT":
        sel_dist = st.selectbox("District", ["Ernakulam (High Court)"], disabled=True)
    else:
        sel_dist = st.selectbox("District", ["Kozhikode", "Tvm", "Thrissur", "Kollam", "Palakkad"])
with c_top3:
    sel_pet = st.selectbox("Petition Type", COURTS[sel_court])

# --- 7. SIDEBAR: ADMIN & HISTORY (Points 4, 15, 19, 20, 21, 30, 36) ---
with st.sidebar:
    st.header("Terminal Control")
    if st.session_state.user == 'admin':
        sel_model = st.selectbox("2.5 Engine", ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]) # Point 30
        if st.button("👁️ View Recent Logins"):
            logs = sb.table("login_history").select("*").order("login_time", desc=True).limit(5).execute()
            for log in logs.data: st.caption(f"👤 {log['username']} | 🕒 {log['login_time'][11:16]}")
        if st.button("📥 Download History CSV"): # Point 21
            logs = sb.table("login_history").select("*").execute()
            df = pd.DataFrame(logs.data)
            st.download_button("Download CSV", df.to_csv(index=False).encode('utf-8'), "login_report.csv", "text/csv")
    else:
        sel_model = "gemini-2.5-flash"
        st.info("🚀 Running: Gemini 2.5 Flash")

    st.divider()
    st.subheader("Last 10 Cases (Vault)") # Point 4/15
    hist = sb.table("legal_drafts").select("*").eq("user", st.session_state.user).order("created_at", desc=True).limit(10).execute()
    for item in hist.data:
        if st.button(f"📅 {item['created_at'][5:10]} | {item['type'][:10]}...", key=item['id']):
            st.session_state.master = item['content']
            st.rerun()

# --- 8. WORKSTATION (Points 5, 6, 7, 8, 9, 10, 11, 13, 14) ---
w1, w2 = st.columns(2)
with w1:
    st.subheader("Case Parameters")
    pa = st.text_input("PARTY A", value=st.session_state.pa_name)
    pb = st.text_input("PARTY B", value=st.session_state.pb_name)
    
    if st.button("🔄 Swap Party A & B", use_container_width=True): # Point 9
        st.session_state.pa_name, st.session_state.pb_name = pb, pa
        st.rerun()
    
    st.markdown(f"🔗 [Research Precedents on Indian Kanoon](https://indiankanoon.org/search/?formInput={sel_pet}+kerala)") # Point 6
    facts = st.text_area("Facts & Mirror Style DNA", height=230) # Point 7
    
    if st.button("🚀 AI Draft", type="primary", use_container_width=True):
        with st.status(f"Consulting {sel_model}...") as s: # Point 13: Timer
            t_start = time.time()
            client = get_engine()
            # Point 8: Strict Party A/B Logic
            prompt = f"Draft {sel_pet} for {pa} vs {pb} in {sel_dist}. Use Professional Kerala Court formatting. Facts: {facts}"
            res = client.models.generate_content(model=sel_model, contents=prompt)
            st.session_state.master = res.text
            s.update(label=f"Completed in {round(time.time()-t_start, 1)}s", state="complete")

with w2:
    st.subheader("Live Editor")
    # Point 11: Large Editable Area
    st.session_state.master = st.text_area("Workstation Editor", value=st.session_state.master, height=450)
    cf, cr = st.columns(2)
    f_w = cf.text_input("Find Word")
    r_w = cr.text_input("Replace With")
    if st.button("Apply Search & Replace"): # Point 10
        st.session_state.master = st.session_state.master.replace(f_w, r_w)
        st.rerun()

# --- 9. EXPORT & CLOUD (Points 12, 16, 19) ---
st.divider()
e1, e2, e3, e4 = st.columns(4)
with e1:
    # Point 19: Only Admin Cloud Save
    if st.button("☁️ Cloud Save", disabled=(st.session_state.user!='admin'), use_container_width=True):
        sb.table("legal_drafts").insert({"user": st.session_state.user, "content": st.session_state.master, "type": sel_pet}).execute()
        st.success("Vault Updated.")
with e2:
    doc = Document(); doc.add_paragraph(st.session_state.master); bio = BytesIO(); doc.save(bio)
    st.download_button("📝 DOCX Export", bio.getvalue(), "draft.docx", use_container_width=True) # Point 12
with e3:
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12); pdf.multi_cell(0, 10, st.session_state.master)
    st.download_button("📄 PDF Export", pdf.output(dest='S'), "draft.pdf", use_container_width=True) # Point 12
with e4:
    if st.button("♻️ Reset Terminal", use_container_width=True): # Point 14
        st.session_state.master = ""; st.session_state.pa_name = "Petitioner"; st.session_state.pb_name = "Respondent"; st.rerun()
