import streamlit as st
from supabase import create_client, Client
import uuid
import time
import pandas as pd
from docx import Document
from io import BytesIO

# --- 1. SETTINGS & UI POLISH (Points 24, 25, 28) ---
st.set_page_config(page_title="Chamber Workstation", layout="wide", initial_sidebar_state="collapsed")

# Hide Developer Tools for non-admins
if 'user_role' in st.session_state and st.session_state.user_role != 'admin':
    st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)

# --- 2. DATABASE & CONNECTION ---
url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- 3. SESSION INITIALIZATION ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'final_master' not in st.session_state: st.session_state.final_master = ""
if 'search_term' not in st.session_state: st.session_state.search_term = ""

# --- 4. LOGIN & KILL SWITCH (Points 17, 26, 27) ---
if not st.session_state.authenticated:
    st.title("👨‍⚖️ Chamber Login")
    with st.form("login"):
        u = st.text_input("User").lower().strip()
        p = st.text_input("Pass", type="password")
        if st.form_submit_button("Access", use_container_width=True):
            creds = st.secrets.get("passwords", {})
            if u in creds and p == creds[u]:
                this_id = str(uuid.uuid4())
                st.session_state.session_id, st.session_state.authenticated, st.session_state.user_role = this_id, True, u
                supabase.table("active_sessions").upsert({"username": u, "session_id": this_id}).execute()
                st.rerun()
    st.stop()

# SESSION GUARD CHECK
check = supabase.table("active_sessions").select("session_id").eq("username", st.session_state.user_role).execute()
if check.data and check.data[0]['session_id'] != st.session_state.session_id:
    st.error("🚨 Account active on another device. Logging out...")
    time.sleep(2)
    st.session_state.authenticated = False
    st.rerun()

# --- 5. COMMAND BAR (Point 27) ---
h1, h2 = st.columns([5, 1])
with h1: st.title(f"⚖️ {st.session_state.user_role.upper()} TERMINAL")
with h2:
    st.write("##")
    if st.button("🚪 Logout", use_container_width=True):
        supabase.table("active_sessions").delete().eq("username", st.session_state.user_role).execute()
        st.session_state.authenticated = False; st.rerun()

st.divider()

# --- 6. DATA LISTS (Points 1, 2, 22, 23) ---
COURT_DATA = {
    "HIGH COURT": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Review Petition", "Arbitration Request"],
    "Family Court": ["Original Petition (OP)", "Maintenance (MC)", "Divorce Petition", "Guardian Petition", "Restitution of Conjugal Rights"],
    "Munsiff Court": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction", "Rent Control Petition"],
    "DISTRICT COURT": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Probate OP"],
    "DVC": ["Domestic Violence Complaint (DIR)"],
    "MC": ["Maintenance Case Section 125"],
    "MVOP": ["Motor Accident Claim"]
}

# --- 7. SIDEBAR (Points 4, 15, 20, 21) ---
with st.sidebar:
    st.header("Settings")
    if st.session_state.user_role == 'admin':
        model = st.selectbox("AI Model", ["Gemini 1.5 Pro", "Gemini 1.5 Flash"])
    
    st.divider()
    sel_court = st.selectbox("Select Court", list(COURT_DATA.keys()))
    
    # HC Auto-Lock (Point 3)
    if sel_court == "HIGH COURT":
        dist = st.selectbox("District", ["Ernakulam (High Court)"], disabled=True)
    else:
        dist = st.selectbox("District", ["Kozhikode", "Thiruvananthapuram", "Kollam", "Thrissur", "Palakkad"])
    
    sel_pet = st.selectbox("Petition Type", COURT_DATA[sel_court])
    
    st.divider()
    st.subheader("History (Last 10)")
    # Sidebar History Placeholder (Point 4)
    if st.session_state.user_role == 'admin':
        st.button("📥 Download History CSV")

# --- 8. DRAFTING TOOLS (Points 8, 9, 10, 11, 13, 14) ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("Case Details")
    p_a = st.text_input("Party A (Petitioner)", key="pa")
    p_b = st.text_input("Party B (Respondent)", key="pb")
    facts = st.text_area("Case Facts", height=300)
    
    if st.button("🚀 Generate AI Draft", use_container_width=True):
        with st.status("Consulting Vault & Drafting...", expanded=True):
            time.sleep(2) # AI Sim
            st.session_state.final_master = f"BEFORE THE {sel_court} AT {dist}\n\nBETWEEN: {p_a} AND {p_b}\n\nREASONING: Based on provided facts..."

with c2:
    st.subheader("Workstation Editor")
    m1, m2 = st.columns(2)
    with m1:
        if st.button("🔄 Swap Parties"):
            st.session_state.pa, st.session_state.pb = st.session_state.pb, st.session_state.pa
            st.rerun()
    with m2:
        search_w = st.text_input("Search/Replace", placeholder="Find word...", key="sw")
    
    # Editable Text Area (Point 11)
    st.session_state.final_master = st.text_area("Live Draft", value=st.session_state.final_master, height=400)

# --- 9. CLOUD SAVE & EXPORT (Points 12, 16, 19) ---
st.divider()
s1, s2, s3 = st.columns(3)
with s1:
    is_admin = st.session_state.user_role == 'admin'
    if st.button("☁️ Cloud Save", type="primary", use_container_width=True, disabled=not is_admin):
        try:
            supabase.table("legal_drafts").insert({
                "client_name": p_a, "draft_type": sel_pet, "draft_content": st.session_state.final_master
            }).execute()
            st.success("Saved to Supabase!")
        except Exception as e: st.error(f"Error: {e}")

with s2:
    st.button("📝 Export to Word (.docx)", use_container_width=True)

with s3:
    if st.button("♻️ Reset Workstation", use_container_width=True):
        st.session_state.final_master = ""
        st.rerun()
