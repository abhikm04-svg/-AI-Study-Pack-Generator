import io
import re
from typing import List, Optional

import google.generativeai as genai
import streamlit as st
from PIL import Image


# --- Page Configuration ---
st.set_page_config(page_title="AI Study Pack Generator", page_icon="🧠", layout="wide")


# --- Material-like Styling ---
st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(180deg, #f5f7fb 0%, #edf2f7 100%);
        }
        .block-container {
            padding-top: 1.2rem;
            max-width: 1200px;
        }
        .hero-card {
            background: white;
            border-radius: 18px;
            padding: 1.2rem 1.4rem;
            box-shadow: 0 6px 18px rgba(20, 33, 61, 0.08);
            border: 1px solid #e6eaf2;
            margin-bottom: 1rem;
        }
        .status-chip {
            display: inline-block;
            margin: 0.2rem 0.35rem 0.2rem 0;
            padding: 0.28rem 0.6rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            border: 1px solid #d9e2f2;
            background: #f8fbff;
            color: #355c92;
        }
        .status-chip.done {
            background: #e9f8ee;
            border-color: #b9eac7;
            color: #1a7f43;
        }
        .status-chip.active {
            background: #e8f0fe;
            border-color: #9cc1ff;
            color: #1148a3;
        }
        .status-chip.todo {
            background: #f6f8fb;
            border-color: #e5eaf3;
            color: #5f6b7a;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


WORKFLOW_STEPS = [
    "Extract content",
    "Generate notes",
    "Create mind map",
    "Build downloads",
]


# --- Fast-load helpers ---
@st.cache_resource(show_spinner=False)
def get_model(model_name: str, system_instruction: Optional[str] = None):
    return genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)


@st.cache_resource(show_spinner=False)
def get_vision_model():
    return genai.GenerativeModel("gemini-2.5-pro")


def update_workflow(step_index: int, label: str):
    st.session_state.workflow_index = step_index
    st.session_state.workflow_label = label


def render_workflow_bar():
    current_idx = st.session_state.get("workflow_index", -1)
    label = st.session_state.get("workflow_label", "Idle")

    done_ratio = max(0.0, min((current_idx + 1) / len(WORKFLOW_STEPS), 1.0))
    st.progress(done_ratio, text=f"Workflow status: {label}")

    chips = []
    for idx, step in enumerate(WORKFLOW_STEPS):
        cls = "todo"
        if idx < current_idx:
            cls = "done"
        elif idx == current_idx:
            cls = "active"
        chips.append(f'<span class="status-chip {cls}">{idx + 1}. {step}</span>')
    st.markdown("".join(chips), unsafe_allow_html=True)


# --- Session State ---
if "generation_complete" not in st.session_state:
    st.session_state.generation_complete = False
if "notes_pdf" not in st.session_state:
    st.session_state.notes_pdf = None
if "mind_map_png" not in st.session_state:
    st.session_state.mind_map_png = None
if "workflow_index" not in st.session_state:
    st.session_state.workflow_index = -1
if "workflow_label" not in st.session_state:
    st.session_state.workflow_label = "Waiting for input"


# --- Header ---
st.markdown(
    """
    <div class="hero-card">
      <h2 style="margin:0 0 0.25rem 0;">🧠 AI Study Pack Generator</h2>
      <p style="margin:0;color:#526071;">Transform class materials into polished notes and a concept map with a guided workflow.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_workflow_bar()

# --- API Key Logic ---
api_key = ""
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    st.success("API key successfully loaded!", icon="✅")
except KeyError:
    st.warning("No API key found in secrets. Enter one below to continue.", icon="🔐")
    api_key = st.text_input("Enter your Gemini API Key", type="password")


# --- Main App ---
if api_key:
    genai.configure(api_key=api_key)

    st.write("Upload notes (.pdf, .docx, .pptx, images) to generate a full study pack.")

    with st.expander("Advanced options"):
        system_message = st.text_area(
            "System message (AI role)",
            "You are an expert academic assistant. Transform notes into a comprehensive, well-structured educational document in Markdown with clear examples.",
        )

    uploaded_files = st.file_uploader(
        "Upload your notes",
        type=["pdf", "docx", "pptx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if st.button("Generate Study Pack", type="primary", use_container_width=True):
        if not uploaded_files:
            st.warning("Please upload notes to get started.")
            st.stop()

        # Lazy imports reduce initial app load time
        import fitz  # PyMuPDF
        import docx
        import graphviz
        import markdown2
        import pdfkit
        import pptx

        final_extracted_content = ""
        images_for_processing: List[Image.Image] = []

        with st.status("Step 1/4: Extracting content...", expanded=True) as status:
            update_workflow(0, "Extracting content")
            for uploaded_file in uploaded_files:
                st.write(f"Processing: {uploaded_file.name}")
                if uploaded_file.type == "application/pdf":
                    pdf_document = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")
                    for page in pdf_document:
                        pix = page.get_pixmap(dpi=120)
                        images_for_processing.append(Image.open(io.BytesIO(pix.tobytes("png"))))
                elif "wordprocessingml" in uploaded_file.type:
                    doc = docx.Document(uploaded_file)
                    final_extracted_content += "\n".join([p.text for p in doc.paragraphs]) + "\n"
                elif "presentationml" in uploaded_file.type:
                    prs = pptx.Presentation(uploaded_file)
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if getattr(shape, "has_text_frame", False):
                                final_extracted_content += shape.text + "\n"
                else:
                    images_for_processing.append(Image.open(uploaded_file))

            if images_for_processing:
                st.write("Images detected, running vision extraction...")
                vision_response = get_vision_model().generate_content([final_extracted_content] + images_for_processing)
                final_extracted_content = vision_response.text

            status.update(label="Content extracted successfully", state="complete")

        with st.status("Step 2/4: Generating notes...", expanded=True) as status:
            update_workflow(1, "Generating comprehensive notes")
            text_model = get_model("gemini-2.5-pro", system_instruction=system_message)
            notes_prompt = (
                "Please expand the extracted class notes into a detailed, structured document with headings,"
                " key concepts, and examples.\n\n---\n"
                f"{final_extracted_content}\n---"
            )
            final_response = text_model.generate_content(notes_prompt, request_options={"timeout": 600})
            generated_notes = final_response.text
            status.update(label="Notes generated", state="complete")

        with st.status("Step 3/4: Creating mind map...", expanded=True) as status:
            update_workflow(2, "Generating concept mind map")
            mindmap_prompt = (
                "Analyze the text and generate a structural mind map in Graphviz DOT format only.\nText:\n---\n"
                f"{generated_notes}"
            )
            mindmap_response = text_model.generate_content(mindmap_prompt)
            match = re.search(r"```dot\s*([\s\S]*?)\s*```", mindmap_response.text, re.MULTILINE)
            if not match:
                st.error("Could not find valid DOT code in the AI response. Please try again.")
                st.stop()
            dot_code = match.group(1).strip()
            status.update(label="Mind map created", state="complete")

        with st.status("Step 4/4: Preparing package...", expanded=True) as status:
            update_workflow(3, "Preparing downloads")
            html_text = markdown2.markdown(generated_notes, extras=["tables", "fenced-code-blocks", "code-friendly"])
            html_with_style = (
                '<html><head><meta charset="utf-8"><style>body{font-family:Inter,Arial,sans-serif;padding:16px;}</style></head>'
                f"<body>{html_text}</body></html>"
            )
            st.session_state.notes_pdf = pdfkit.from_string(
                html_with_style,
                False,
                options={"enable-local-file-access": ""},
            )

            st.session_state.mind_map_png = graphviz.Source(dot_code).pipe(format="png")
            st.session_state.generation_complete = True
            status.update(label="Downloads are ready", state="complete")

        update_workflow(4, "Complete")
        st.rerun()


if st.session_state.generation_complete:
    st.header("Your Study Pack is Ready!", divider="rainbow")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Generated Notes (PDF)")
        st.download_button(
            label="Download Notes PDF",
            data=st.session_state.notes_pdf,
            file_name="Generated_Notes.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with col2:
        st.subheader("🗺️ Concept Mind Map")
        st.image(st.session_state.mind_map_png)
        st.download_button(
            label="Download Mind Map PNG",
            data=st.session_state.mind_map_png,
            file_name="Concept_Mind_Map.png",
            mime="image/png",
            use_container_width=True,
        )
elif not api_key:
    st.info("Please provide an API key to use the app.")
