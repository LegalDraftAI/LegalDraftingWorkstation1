import streamlit as st
import time, uuid, pandas as pd
from io import BytesIO
from docx import Document
from fpdf import FPDF
from supabase import create_client
from google import genai

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Chamber Terminal 2026", layout="wide", initial_sidebar_state="collapsed")

# Initialize session states with explicit keys
if "master" not in st.session_state: st.session_state.master = ""
if "auth" not in st.session_state: st.session_state.auth = False
if "user" not in st.session_state: st.session_state.user = ""
if "dna_sample" not in st.session_state: st.session_state.dna_sample = ""

# --- 2. DATASET ---
DISTRICTS = ["Kozhikode", "Thiruvananthapuram", "Ernakulam", "Thrissur", "Kollam", "Palakkad", "Malappuram", "Kannur", "Alappuzha", "Kottayam", "Idukki", "Wayanad", "Pathanamthitta", "Kasaragod"]
COURT_CONFIG = {
    "HIGH COURT": {"dist": ["Ernakulam (High Court)"], "petitions": ["Writ Petition (Civil)", "Writ Petition (Criminal)", "Bail Application", "Review Petition"]},
    "Family Court": {"dist": DISTRICTS, "petitions": ["OP (Divorce)", "OP (Restitution)", "MC (Maintenance)", "Guardian Petition"]},
    "Munsiff Court": {"dist": DISTRICTS, "petitions": ["Original Suit (OS)", "Execution Petition (EP)", "Injunction Application"]},
    "DISTRICT COURT": {"dist": DISTRICTS, "petitions": ["Civil Appeal", "Criminal Appeal", "Sessions Case", "Motor Accident Claim"]},
    "DVC / MC / MVOP": {"dist": DISTRICTS, "petitions": ["Domestic Violence (DIR)", "Section 125 MC", "MVOP Claim"]}
}

# --- 3. DATABASE & AI ENGINE ---
@st.cache_resource
def init_db():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

def get_engine():
    m_key = st.secrets.get("GEMINI_KEY")
    return genai.Client(api_key=m_key)

MODEL_MAP = {"Gemini 2.5 Flash": "gemini-2.0-flash", "Gemini 2.5 Pro": "gemini-2.0-pro-exp-02-05"}

# --- 4. LOGIN & KILL SWITCH ---
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
                    db.table("active_sessions").delete().eq("username", u_in).execute()
                    db.table("active_sessions").insert({"username": u_in, "session_id": new_sid}).execute()
                except: pass
            st.session_state.update({"auth": True, "user": u_in, "sid": new_sid})
            st.rerun()
    st.stop()

# --- 5. COMMAND BAR ---
t1, t2 = st.columns([0.8, 0.2])
with t1: st.title(f"⚖️ {st.session_state.user.upper()} WORKSTATION")
with t2:
    if st.button("🚪 Logout", use_container_width=True):
        if db:
            try: db.table("active_sessions").delete().eq("username", st.session_state.user).execute()
            except: pass
        st.session_state.auth = False; st.rerun()

c1, c2, c3 = st.columns(3)
with c1: sel_court = st.selectbox("Court", list(COURT_CONFIG.keys()))
with c2: sel_dist = st.selectbox("District", COURT_CONFIG[sel_court]["dist"])
with c3: sel_pet = st.selectbox("Petition Type", COURT_CONFIG[sel_court]["petitions"])

# --- 6. SIDEBAR & STYLE VAULT ---
with st.sidebar:
    if st.session_state.user == 'admin':
        curr_model = MODEL_MAP[st.selectbox("Engine", list(MODEL_MAP.keys()))]
    else:
        st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)
        curr_model = "gemini-2.0-flash"
    
    st.divider(); st.subheader("📂 STYLE VAULT")
    if db:
        try:
            hist = db.table("legal_drafts").select("*").eq("username", st.session_state.user).order("id", desc=True).limit(10).execute()
            for item in hist.data:
                if st.button(f"📄 {item['type'][:12]}...", key=f"h_{item['id']}"):
                    st.session_state.master = item['content']
                    st.session_state.dna_sample = item['content']
                    st.rerun()
        except: pass

# --- 7. WORKSTATION & HARDENED AI LOGIC ---
w1, w2 = st.columns(2)
with w1:
    st.subheader("Case DNA")
    pa = st.text_input("PARTY A", value="Petitioner")
    pb = st.text_input("PARTY B", value="Respondent")
    facts = st.text_area("Case Facts", height=200, placeholder="Describe the incident/legal matter...")
    
    if st.button("🚀 AI Draft", type="primary", use_container_width=True):
        if not facts:
            st.error("Please enter facts first.")
        else:
            msg_placeholder = st.empty()
            msg_placeholder.info("⏳ Engine Consulting... Please wait.")
            try:
                dna_text = f"STYLE REFERENCE: {st.session_state.dna_sample[:1000]}" if st.session_state.dna_sample else ""
                full_prompt = f"{dna_text}\n\nTask: Draft a formal {sel_pet} for {sel_court} in {sel_dist}. PARTY A: {pa}, PARTY B: {pb}. Facts: {facts}\n\nLEGAL DRAFT:"
                
                client = get_engine()
                # Use a more direct generation call
                response = client.models.generate_content(model=curr_model, contents=full_prompt)
                
                # Verify text presence
                if response.text:
                    st.session_state.master = response.text
                    msg_placeholder.success("✅ Drafting Complete!")
                    time.sleep(1) # Allow state to stabilize
                    st.rerun()
                else:
                    msg_placeholder.error("❌ AI returned no text. Check API quota/Safety filters.")
            except Exception as e:
                msg_placeholder.error(f"❌ Engine Error: {str(e)}")

with w2:
    st.subheader("Live Editor")
    # THE KEY FIX: Using a key for the text area and referencing session_state directly
    st.session_state.master = st.text_area(
        "Editor", 
        value=st.session_state.master, 
        height=500, 
        key="main_editor_widget"
    )

# --- 8. EXPORTS ---
st.divider()
e1, e2, e3, e4 = st.columns(4)
with e1:
    if st.button("☁️ Cloud Save", disabled=(st.session_state.user != 'admin'), use_container_width=True):
        if db:
            db.table("legal_drafts").insert({"username": st.session_state.user, "content": st.session_state.master, "type": sel_pet}).execute()
            st.success("Saved to Cloud.")
with e2:
    doc = Document(); doc.add_paragraph(st.session_state.master); bio = BytesIO(); doc.save(bio)
    st.download_button("📝 DOCX Export", bio.getvalue(), "draft.docx", use_container_width=True)
with e3:
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12); pdf.multi_cell(0, 10, st.session_state.master.encode('latin-1', 'replace').decode('latin-1'))
    st.download_button("📄 PDF Export", pdf.output(dest='S'), "draft.pdf", use_container_width=True)
with e4:
    if st.button("♻️ Reset Workspace", use_container_width=True):
        st.session_state.master = ""; st.rerun()
