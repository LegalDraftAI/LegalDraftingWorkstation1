import streamlit as st
import os
from google import genai
from dotenv import load_dotenv

# 1. Setup
load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

st.set_page_config(page_title="Senior's Legal Assistant", layout="centered")
st.title("⚖️ Senior's Drafting Assistant")

# Initialize "Memory" (Session State)
if "current_draft" not in st.session_state:
    st.session_state.current_draft = ""

# --- SECTION 1: INITIAL DRAFTING ---
st.subheader("1. Start a New Draft")
main_prompt = st.text_area("Initial instructions (e.g., Partnership Deed for a Law Firm):", height=100)

if st.button("Generate Initial Draft"):
    if main_prompt:
        with st.spinner("Drafting..."):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=f"You are a senior lawyer. Draft a formal document: {main_prompt}"
                )
                st.session_state.current_draft = response.text
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Please enter instructions.")

# --- SECTION 2: THE WORKING DRAFT ---
if st.session_state.current_draft:
    st.divider()
    st.subheader("2. Current Draft")
    
    # Display the draft in a box
    st.markdown(st.session_state.current_draft)
    
    # DOWNLOAD BUTTON
    st.download_button(
        label="📥 Download Draft as Text",
        data=st.session_state.current_draft,
        file_name="legal_draft.txt",
        mime="text/plain"
    )

    # --- SECTION 3: REFINEMENT ---
    st.divider()
    st.subheader("3. Refine this Draft")
    refine_input = st.text_input("Add specific clauses or changes (e.g., 'Add a 30-day notice period for termination'):")
    
    if st.button("Apply Changes"):
        if refine_input:
            with st.spinner("Updating draft..."):
                try:
                    # We send the OLD draft + the NEW instructions back to Gemini
                    refine_prompt = f"""
                    Here is the existing legal draft:
                    {st.session_state.current_draft}
                    
                    Please update it with these specific instructions:
                    {refine_input}
                    
                    Provide the full updated draft.
                    """
                    response = client.models.generate_content(
                        model='gemini-2.0-flash', 
                        contents=refine_prompt
                    )
                    st.session_state.current_draft = response.text
                    st.rerun() # Refresh to show the new version
                except Exception as e:
                    st.error(f"Error: {e}")

