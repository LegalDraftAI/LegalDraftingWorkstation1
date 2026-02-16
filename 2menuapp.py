import streamlit as st
import os
import requests
import pandas as pd
from datetime import datetime
from google import genai
from dotenv import load_dotenv
from docx import Document
from fpdf import FPDF
import io

# 1. INITIAL SETUP
load_dotenv()
INITIAL_G_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
INITIAL_IK_TOKEN = os.getenv("INDIAN_KANOON_TOKEN", "").strip()
HISTORY_FILE = "kerala_case_history.csv"

st.set_page_config(page_title="Kerala Senior Advocate Workstation", layout="wide")

# 2. SESSION STATE (The "Sticky" Memory)
if "google_key" not in st.session_state: st.session_state.google_key = INITIAL_G_KEY
if "ik_token" not in st.session_state: st.session_state.ik_token = INITIAL_IK_TOKEN
if "final_master" not in st.session_state: st.session_state.final_master = ""
if "search_results" not in st.session_state: st.session_state.search_results = [] # FIXED: Persists results

KERALA_DISTRICTS = ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Pathanamthitta", "Thiruvananthapuram", "Thrissur", "Wayanad"]

# 3. EXPORT HELPERS
def generate_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def generate_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    safe_text = text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, txt=safe_text)
    return pdf.output(dest='S').encode('latin-1')

# 4. INTERFACE TABS
tab_work, tab_settings = st.tabs(["⚖️ Workstation", "⚙️ Settings"])

with tab_settings:
    st.header("🔑 API Settings")
    st.session_state.google_key = st.text_input("Gemini API Key", value=st.session_state.google_key, type="password")
    st.session_state.ik_token = st.text_input("Indian Kanoon Token", value=st.session_state.ik_token, type="password")
    if st.button("💾 Save Settings"): st.rerun()

with tab_work:
    with st.sidebar:
        st.title("👨‍⚖️ Kerala Admin")
        doc_type = st.selectbox("Petition Type", ["Bail Application", "Legal Notice", "Maintenance Petition", "Divorce Petition", "Writ Petition"])
        jurisdiction = st.selectbox("Court Level", ["High Court", "District Court", "Family Court"])
        
        # --- KERALA LOGIC: DISABLE DISTRICT FOR HIGH COURT ---
        is_hc = (jurisdiction == "High Court")
        selected_district = st.selectbox(
            "Select District", 
            KERALA_DISTRICTS, 
            index=KERALA_DISTRICTS.index("Ernakulam") if is_hc else 0,
            disabled=is_hc,
            help="High Court is centralized in Kochi (Ernakulam)."
        )
        
        st.divider()
        if len(st.session_state.ik_token) > 5: st.success("🟢 Senior Mode: Live")
        else: st.warning("🧪 Intern Mode: Mocking")

    st.title(f"Drafting: {doc_type}")
    facts = st.text_area("Case Facts:", placeholder="Enter case details for the Kerala jurisdiction...", height=150)

    # ACTION BUTTONS
    c1, c2, _ = st.columns([1, 1, 3])
    
    with c1:
        if st.button("🔍 Search Cases", use_container_width=True):
            if len(st.session_state.ik_token) < 5:
                # Mock Data for testing
                st.session_state.search_results = [
                    {"title": "Sunil v. State of Kerala (2023)", "headline": "Clarification on Section 438 CrPC in Kerala High Court."},
                    {"title": "Mary v. Joseph (Family Court EKM)", "headline": "Interim maintenance guidelines for Kerala Family Courts."}
                ]
            else:
                try:
                    headers = {'Authorization': f'Token {st.session_state.ik_token}'}
                    r = requests.post(f"https://api.indiankanoon.org/search/?formInput={facts}", headers=headers)
                    if r.status_code == 200:
                        st.session_state.search_results = r.json().get('docs', [])
                except: st.error("Kanoon API Error")
            st.rerun()

    with c2:
        if st.button("🚀 Draft Petition", type="primary", use_container_width=True):
            if not st.session_state.google_key:
                st.error("Please add Gemini Key in Settings!")
            else:
                client = genai.Client(api_key=st.session_state.google_key)
                court_label = "THE HIGH COURT OF KERALA AT ERNAKULAM" if is_hc else f"THE {jurisdiction.upper()} AT {selected_district.upper()}, KERALA"
                
                full_prompt = f"""
                Act as a Senior Advocate of the Kerala High Court.
                Draft a formal {doc_type} for {court_label}.
                
                STRUCTURE:
                1. IN {court_label}
                2. Petitioner vs Respondent section
                3. Petition under relevant Sections of Indian Law
                4. Most Respectfully Showeth: (Chronological facts)
                5. Prayer: Formal request to the court.
                
                Facts provided: {facts}
                """
                res = client.models.generate_content(model='gemini-1.5-flash', contents=full_prompt)
                st.session_state.final_master = res.text
                st.rerun()

    # --- DISPLAY SEARCH RESULTS (Persistent) ---
    if st.session_state.search_results:
        with st.expander("📚 Relevant Kerala Precedents", expanded=True):
            for doc in st.session_state.search_results[:3]:
                st.markdown(f"**{doc.get('title')}**")
                st.caption(doc.get('headline'))
                st.divider()

    # --- FINAL EDITABLE WORKSPACE ---
    if st.session_state.final_master:
        st.divider()
        st.subheader("📜 Live Editor & Export")
        
        # Lawyer edits here
        edited_text = st.text_area("Finalize Petition Draft:", value=st.session_state.final_master, height=500)
        
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            if st.button("💾 Save to History"):
                pd.DataFrame([{"Date": datetime.now(), "Type": doc_type, "Draft": edited_text}]).to_csv(HISTORY_FILE, mode='a', header=not os.path.exists(HISTORY_FILE), index=False)
                st.success("Draft Saved Locally!")
        with ec2:
            st.download_button("📥 Word (.docx)", data=generate_docx(edited_text), file_name=f"Kerala_{doc_type}.docx")
        with ec3:
            st.download_button("📥 PDF (.pdf)", data=generate_pdf(edited_text), file_name=f"Kerala_{doc_type}.pdf")