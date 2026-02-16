import streamlit as st
import os
import time
from google import genai
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# 1. LOAD API KEY
load_dotenv(override=True)
api_key = os.getenv("GOOGLE_API_KEY")

st.set_page_config(page_title="Senior's Legal Assistant", layout="wide")

# 2. SESSION MEMORY (Prevents screen clearing when clicking buttons)
if "res" not in st.session_state: st.session_state.res = ""
if "draft" not in st.session_state: st.session_state.draft = ""

# 3. GEMINI 2.0 FLASH LOGIC (With Error Protection)
def run_ai(text):
    if not api_key:
        return "❌ Error: API Key missing from .env file."
    try:
        client = genai.Client(api_key=api_key)
        # Using Gemini 2.0 Flash - The fastest and latest model
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=text
        )
        return response.text
    except Exception as e:
        if "429" in str(e):
            return "⚠️ Server Busy. Please wait 15 seconds and try again."
        return f"❌ AI Error: {str(e)}"

# 4. SEARCH LOGIC (Strictly Indian Courts)
def run_search(query, target):
    if target == "KANOON":
        q = f"site:indiankanoon.org {query} judgement"
    elif target == "KERALA":
        q = f"site:hckerala.gov.in {query}"
    else:
        q = f"{query} Indian court law precedent"

    try:
        with DDGS() as ddgs:
            # region='in-en' forces Indian English results and avoids Chinese sites
            results = list(ddgs.text(q, region='in-en', max_results=5))
            if not results:
                return "⚠️ No specific Indian records found for this query."
            
            out = ""
            for r in results:
                # Manual filter to block non-Indian irrelevant sites
                if any(x in r['href'] for x in ["zhihu", "baidu", "wikipedia"]): continue
                out += f"📍 **{r['title']}**\n\nLink: {r['href']}\n\n{r['body']}\n\n---\n\n"
            return out if out else "⚠️ No relevant results found."
    except Exception:
        return "❌ Search tool temporarily unavailable. Try again in 30 seconds."

# --- UI INTERFACE ---
st.title("⚖️ Senior's Drafting Assistant")
st.caption("Powered by Gemini 2.0 Flash | Indian Law Edition")

user_query = st.text_input("Enter Section, Case Name, or Legal Issue:", placeholder="e.g. 138 NI Act liability of sleeping director")

# THE 4 BUTTONS
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("🤖 AI Quick Draft"):
        with st.spinner("Writing..."):
            st.session_state.draft = run_ai(f"Draft a professional legal document for: {user_query}")
with c2:
    if st.button("📜 Search Kanoon"):
        with st.spinner("Scanning Kanoon..."):
            st.session_state.res = run_search(user_query, "KANOON")
with c3:
    if st.button("🌐 Web Search"):
        with st.spinner("Scanning Web..."):
            st.session_state.res = run_search(user_query, "WEB")
with c4:
    if st.button("🌴 Kerala HC"):
        with st.spinner("Scanning High Court..."):
            st.session_state.res = run_search(user_query, "KERALA")

st.divider()

# DISPLAY AREA
left, right = st.columns(2)
with left:
    st.subheader("🔍 Research Findings")
    if st.session_state.res:
        st.markdown(st.session_state.res)
        if st.button("🪄 Convert Research to Draft"):
            with st.spinner("Drafting..."):
                prompt = f"Based on this research:\n{st.session_state.res}\n\nDraft a document for: {user_query}"
                st.session_state.draft = run_ai(prompt)
    else:
        st.write("Research results will appear here.")

with right:
    st.subheader("📝 Final Draft")
    if st.session_state.draft:
        st.session_state.draft = st.text_area("Review & Edit:", value=st.session_state.draft, height=500)
    else:
        st.info("Your draft will appear here.")