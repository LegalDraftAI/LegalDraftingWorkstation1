import streamlit as st
import time, uuid
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client
from google import genai

# --- 1. SETTINGS & PLUMBING ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""
if 'master' not in st.session_state: st.session_state.master = ""

# --- 2. DISTRICTS & DATA (Point 1, 22, 23) ---
KERALA_DISTRICTS = ["Kozhikode", "Thiruvananthapuram", "Ernakulam", "Thrissur", "Kollam", "Palakkad", "Malappuram", "Kannur", "Alappuzha", "Kottayam", "Idukki", "Wayanad", "Pathanamthitta", "Kasaragod"]

COURT_CONFIG = {
    "HIGH COURT": {"districts": ["Ernakulam (High Court)"], "types": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Review Petition", "Arb. Request"]},
    "Family Court": {"districts": KERALA_DISTRICTS, "types": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition"]},
    "Munsiff Court": {"districts": KERALA_DISTRICTS, "types": ["Original Suit (OS)", "Execution Petition (EP)", "Rent Control"]},
    "DISTRICT COURT": {"districts": KERALA_DISTRICTS, "types": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Probate OP"]},
    "DVC/MC/MVOP": {"districts": KERALA_DISTRICTS, "types": ["Domestic Violence (DIR)", "Maintenance Case", "Motor Accident Claim"]}
}

@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def get_engine():
    raw_keys = st.secrets.get("API_KEYS", [])
    valid_keys = [k[1] for k in raw_keys if len(k) > 1]
    idx = int(time.time()) % len(valid_keys) if valid_keys else 0
    return genai.Client(api_key=valid_keys[idx] if valid_keys else st.secrets["GEMINI_KEY"])

# --- 3. LOGIN GATE (History Logging Fixed) ---
if not st.session_state.auth:
    st.title("⚖️ Chamber Terminal Access")
    u_in = st.text_input("User ID").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("Enter Terminal", use_container_width=True):
        creds = st.secrets.get("passwords", {})
        if u_in in creds and str(p_in) == str(creds[u_in]):
            # START LOGGING
            try:
                init_db().table("login_history").insert({"username": u_in}).execute()
            except Exception as e:
                st.warning(f"Note: Login recorded locally only. (DB: {str(e)})")
            
            st.session_state.update({"auth": True, "user": u_in})
            st.rerun()
    st.stop()

# --- 4. TOP NAV & LOGOUT (Point 27, 38) ---
t_col1, t_col2 = st.columns([0.8, 0.2])
with t_col1:
    st.title(f"⚖️ {st.session_state.user.upper()} WORKSTATION")
with t_col2:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- 5. COURT SELECTORS (Point 38) ---
c1, c2, c3 = st.columns(3)
with c1:
    sel_court = st.selectbox("Select Court", list(COURT_CONFIG.keys()))
with c2:
    sel_dist = st.selectbox("District", COURT_CONFIG[sel_court]["districts"])
with c3:
    sel_pet = st.selectbox("Petition Type", COURT_CONFIG[sel_court]["types"])

st.divider()

# --- 6. SIDEBAR: ADMIN ONLY (Point 20, 24, 30) ---
with st.sidebar:
    if st.session_state.user == 'admin':
        st.header("🔑 Admin Panel")
        sel_model = st.selectbox("Engine Suite", ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"])
        if st.button("👁️ Audit Logins"):
            try:
                logs = init_db().table("login_history").select("*").order("id",
