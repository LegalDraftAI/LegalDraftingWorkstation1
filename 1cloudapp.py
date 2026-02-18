import streamlit as st
import time, uuid, pandas as pd
from datetime import datetime
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client, Client
from google import genai

# --- 1. CORE UI & SECURITY CONFIG (Points 24, 25, 28) ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

def apply_ui_security(role):
    if role != 'admin':
        # Point 24: Hide all developer tools, icons, and menus for Juniors/Seniors
        hide_style = """
        <style>
        #MainMenu, footer, header {visibility: hidden;}
        .stDeployButton {display:none;}
        [data-testid="stToolbar"] {visibility: hidden !important;}
        </style>
        """
        st.markdown(hide_style, unsafe_allow_html=True)

# --- 2. DATABASE & ROTATION ENGINE (Points 18, 29, 31, 32, 37) ---
@st.cache_resource
def init_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

sb = init_db()

def get_engine():
    # Point 18 & 31: 5-Key Smart Rotation
    raw_keys = st.secrets.get("API_KEYS", [])
    valid_keys = [k[1] for k in raw_keys if k[1] and len(k[1]) > 10]
    if not valid_keys:
        st.error("No API Keys Found")
        st.stop()
    idx = int(time.time()) % len(valid_keys)
    return genai.Client(api_key=valid_keys[idx])

# --- 3. EXPANDED KERALA COURT DATA (Points 1, 2, 3, 22, 23) ---
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
if 'auth' not in st.session_state:
    st.session_state.auth = False

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
            st.session_state.update({"auth":True, "user":u_in, "sid":sid, "master":""})
            st.rerun()
    st.stop()

# Kill Switch Check (Continuous Security)
check = sb.table("active_sessions").select("session_id").eq("username", st.session_state.user).execute()
if check.data and check.data[0]['session_id'] != st.session_state.sid:
    st.error("🚨 Access Revoked: Account active elsewhere.")
    st.session_state.auth = False
    time.sleep(2)
    st.rerun()

apply_ui_security(st.session_state.user)

# --- 5. COMMAND BAR (Point 27) ---
c1,
