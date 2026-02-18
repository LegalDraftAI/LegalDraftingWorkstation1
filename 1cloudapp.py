import streamlit as st
import time, uuid, pandas as pd
from datetime import datetime
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client, Client
from google import genai

# --- 1. CORE CONFIG & SECURITY (Points 24, 25, 28) ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = None

def apply_ui_security():
    if st.session_state.user != 'admin':
        st.markdown("""<style>
            #MainMenu, footer, header {visibility: hidden;}
            .stDeployButton {display:none;}
            [data-testid="stToolbar"] {visibility: hidden !important;}
            </style>""", unsafe_allow_html=True)

# --- 2. DATABASE & ROTATION (Points 18, 31, 32, 37) ---
@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def get_engine():
    raw_keys = st.secrets.get("API_KEYS", [])
    valid_keys = [k[1] for k in raw_keys if k[1] and len(k[1]) > 10]
    idx = int(time.time()) % len(valid_keys)
    return genai.Client(api_key=valid_keys[idx])

COURTS = {
    "HIGH COURT": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Review Petition"],
    "Family Court": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition"],
    "Munsiff Court": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction Application"],
    "DISTRICT COURT": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Motor Accident Claim"],
    "DVC/MC/MVOP": ["DVC (Domestic Violence)", "MC (Maintenance Case)", "MVOP (Motor Accident)"]
}

# --- 3. AUTHENTICATION (Points 17, 21, 26, 34, 35) ---
if not st.session_state.auth:
    st.title("⚖️ Chamber Terminal Access")
    u_in = st.text_input("User ID").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("Enter Terminal", use_container_width=True):
        creds = st.secrets.get("passwords", {})
        if u_in in creds and p_in == creds[u_in]:
            sid = str(uuid.uuid4())
            sb.table("active_sessions").upsert({"username": u_in, "session_id": sid}).execute()
            sb.table("login_history").insert({"username": u_in, "session_id": sid}).execute()
            st.session_state.update({"auth": True, "user": u_in, "sid": sid, "master": ""})
            st.rerun()
    st.stop()

# Kill Switch Check
check = sb.table("active_sessions").select("session_id").eq("username", st.session_state.user).execute()
if check.data and check.data[0]['session_id'] != st.session_state.sid:
    st.session_state.auth = False; st.error("🚨 Session Expired."); time.sleep(2); st.rerun()

apply_ui_security()

# --- 4. MAIN INTERFACE: SELECTORS (Point 38) ---
st.title(f"⚖️ {st.session_state.user.upper()} WORKSTATION")
c_top1, c_top2, c_top3 = st.columns(3)
with c_top1:
    sel_court = st.selectbox("Select Court", list(COURTS.keys()))
with c_top2:
    if sel_court == "HIGH COURT":
        sel_dist = st.selectbox("District", ["Ernakulam (High Court)"], disabled=True)
    else:
        sel_dist = st.selectbox("District", ["Kozhikode", "Tvm", "Thrissur", "Kollam", "Palakkad"])
with c_top3:
    sel_pet = st.selectbox("Petition Type", COURTS[sel_court])

st.divider()

# --- 5. SIDEBAR: ADMIN & VAULT ONLY ---
with st.sidebar:
    st.header("Control Panel")
    # Point 20: Admin Only Model Selection
    if st.session_state.user == 'admin':
        sel_model = st.selectbox("2.5 Engine Suite", ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"])
        if st.button("👁️ View Login History"):
            logs = sb.table("login_history").select("*").order("login_time", desc=True).limit(5).execute()
            for log in logs.data: st.caption(f"👤 {log['username']} | {log['login_time'][11:16]}")
    else:
        sel_model = "gemini-2.5-flash"
        st.info("🚀 Gemini 2.5 Flash Active")
    
    st.divider()
    st.subheader("Last 10 Cases")
    hist = sb.table("legal_drafts").select("*").eq("user", st.session_state.user).order("created_at", desc=True).limit(10).execute()
    for item in hist.data:
        if st.button(f"📅 {item['created_at'][5:10]} | {item['type'][:10]}", key=item['id']):
            st.session_state.master = item['content']; st.rerun()

# --- 6. WORKSTATION & EXPORTS ---
w1, w2 = st.columns(2)
with w1:
    st.subheader("Case DNA")
    pa = st.text_input("PARTY A", value="Petitioner")
    pb = st.text_input("PARTY B", value="Respondent")
    facts = st.text_area("Case Facts", height=230)
    
    if st.button("🚀 AI Draft", type="primary", use_container_width=True):
        with st.status(f"Consulting {sel_model}...") as s:
            t_start = time.time()
            res = get_engine().models.generate_content(model=sel_model, contents=f"Draft {sel_pet} for {pa} vs {pb}. Facts: {facts}")
            st.session_state.master = res.text
            s.update(label=f"Done in {round(time.time()-t_start, 1)}s", state="complete")

with w2:
    st.subheader("Live Editor")
    st.session_state.master = st.text_area("Editor", value=st.session_state.master, height=450)
    if st.button("🚪 Logout", use_container_width=True):
        sb.table("active_sessions").delete().eq("username", st.session_state.user).execute()
        st.session_state.auth = False; st.rerun()

# --- 7. FOOTER: EXPORTS ---
st.divider()
e1, e2, e3, e4 = st.columns(4)
with e1:
    if st.button("☁️ Cloud Save", disabled=(st.session_state.user!='admin'), use_container_width=True):
        sb.table("legal_drafts").insert({"user": st.session_state.user, "content": st.session_state.master, "type": sel_pet}).execute
