# app.py

import streamlit as st
import google.generativeai as genai
import time
import re
import os
import io

# Import tools for file processing
import fitz  # PyMuPDF
import docx
import pptx
import markdown2
import pdfkit
import graphviz
from PIL import Image

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Study Pack Generator",
    page_icon="🧠",
    layout="wide"
)

# --- Initialize Session State ---
# This ensures variables persist between reruns
if 'generation_complete' not in st.session_state:
    st.session_state.generation_complete = False
if 'notes_pdf' not in st.session_state:
    st.session_state.notes_pdf = None
if 'mind_map_png' not in st.session_state:
    st.session_state.mind_map_png = None


# --- App Header ---
st.title("🧠 AI Study Pack Generator")

# --- API Key Logic ---
api_key = ""
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.success("API key successfully loaded!", icon="✅")
except KeyError:
    st.error("API key not found. Please add your key below to proceed.", icon="❌")
    api_key = st.text_input("Enter your Gemini API Key here:", type="password")

# --- Main App Logic ---
if api_key:
    genai.configure(api_key=api_key)

    st.write("Upload your class notes (.pdf, .docx, .pptx, images) and get a complete study package: comprehensive notes and a concept mind map!")
    
    with st.expander("Advanced Options"):
        system_message = st.text_area(
            "System Message (AI's Role)",
            "You are an expert academic assistant. Your goal is to transform notes into a comprehensive, well-structured educational document. Elaborate on topics, add examples, and clarify complex concepts in Markdown format."
        )

    uploaded_files = st.file_uploader(
        "Upload your notes here",
        type=['pdf', 'docx', 'pptx', 'png', 'jpg', 'jpeg'],
        accept_multiple_files=True
    )

    if st.button("Generate Study Pack", type="primary", use_container_width=True):
        if uploaded_files:
            # --- 1. Content Extraction ---
            with st.status("Step 1/4: Extracting content...", expanded=True) as status:
                # (Extraction logic is the same)
                final_extracted_content = ""
                images_for_processing = []
                for uploaded_file in uploaded_files:
                    # ... (file processing logic) ...
                    st.write(f"Processing: {uploaded_file.name}")
                    if uploaded_file.type == "application/pdf":
                        pdf_bytes = uploaded_file.getvalue()
                        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
                        for page in pdf_document:
                            pix = page.get_pixmap(dpi=150)
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            images_for_processing.append(img)
                    elif "wordprocessingml" in uploaded_file.type:
                        doc = docx.Document(uploaded_file)
                        final_extracted_content += "\n".join([p.text for p in doc.paragraphs])
                    elif "presentationml" in uploaded_file.type:
                        prs = pptx.Presentation(uploaded_file)
                        for slide in prs.slides:
                            for shape in slide.shapes:
                                if shape.has_text_frame:
                                    final_extracted_content += shape.text + "\n"
                    else:
                        images_for_processing.append(Image.open(uploaded_file))
                
                if images_for_processing:
                    st.write("Images detected, preparing for vision analysis...")
                    model_input = [final_extracted_content] + images_for_processing
                    vision_model = genai.GenerativeModel('gemini-2.5-pro')
                    vision_response = vision_model.generate_content(model_input)
                    final_extracted_content = vision_response.text
                
                status.update(label="Content extracted successfully!", state="complete")

            # --- 2. Generate Comprehensive Notes ---
            with st.status("Step 2/4: Generating notes...", expanded=True) as status:
                text_model = genai.GenerativeModel(model_name='gemini-2.5-pro', system_instruction=system_message)
                notes_prompt = f"Please take the following extracted class notes and expand them into a detailed, comprehensive document...\n\n---\n{final_extracted_content}\n---"
                final_response = text_model.generate_content(notes_prompt, request_options={'timeout': 600})
                generated_notes = final_response.text
                status.update(label="Notes generated!", state="complete")
            
            # --- 3. Generate Mind Map ---
            with st.status("Step 3/4: Creating mind map...", expanded=True) as status:
                time.sleep(20)
                mindmap_prompt = f"Analyze the following text and generate a structural mind map in Graphviz DOT language...\nText:\n---\n{generated_notes}"
                mindmap_response = text_model.generate_content(mindmap_prompt)
                dot_code = re.sub(r'```dot\s*|```', '', mindmap_response.text).strip()
                status.update(label="Mind map created!", state="complete")

            # --- 4. Prepare and Store in Session State ---
            with st.status("Step 4/4: Preparing package...", expanded=True) as status:
                # Create PDF in memory
                html_text = markdown2.markdown(generated_notes, extras=["tables", "fenced-code-blocks", "code-friendly"])
                html_with_style = f'<html><head><meta charset="utf-8"><style>body{{font-family: Arial, sans-serif;}}</style></head><body>{html_text}</body></html>'
                pdf_bytes = pdfkit.from_string(html_with_style, False, options={"enable-local-file-access": ""})
                st.session_state.notes_pdf = pdf_bytes # Save to state

                # Create Mind Map in memory
                src = graphviz.Source(dot_code)
                png_bytes = src.pipe(format='png')
                st.session_state.mind_map_png = png_bytes # Save to state
                
                st.session_state.generation_complete = True # Set flag
                status.update(label="Downloads are ready!", state="complete")
        else:
            st.warning("Please upload your notes to get started.")

# --- Display Results and Download Buttons (if generation is complete) ---
if st.session_state.generation_complete:
    st.header("Your Study Pack is Ready!", divider="rainbow")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Generated Notes (PDF)")
        st.download_button(
            label="Download Notes PDF",
            data=st.session_state.notes_pdf, # Download from state
            file_name="Generated_Notes.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with col2:
        st.subheader("🗺️ Concept Mind Map")
        st.image(st.session_state.mind_map_png) # Display from state
        st.download_button(
            label="Download Mind Map PNG",
            data=st.session_state.mind_map_png, # Download from state
            file_name="Concept_Mind_Map.png",
            mime="image/png",
            use_container_width=True
        )
else:
    # This message shows if the API key is not in secrets and the user hasn't entered one yet.
    if not api_key:
        st.info("Please provide an API key to use the app.")