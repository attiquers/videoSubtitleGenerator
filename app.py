import os
import tempfile
import streamlit as st
from huggingface_hub import snapshot_download

from subtitle_core import extract_audio, transcribe, render_subtitled_video
from srt_tools import to_srt, from_srt

# --------------------- CONFIG ---------------------
st.set_page_config(layout="wide")
st.title("🎬 AI Subtitle Generator")
models_dir = "models"
os.makedirs(models_dir, exist_ok=True)

ALL_MODELS = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base.en": "Systran/faster-whisper-base.en",
    "small.en": "Systran/faster-whisper-small.en",
    "medium.en": "Systran/faster-whisper-medium.en",
}

# --------------------- MODEL SELECTION ---------------------
def is_model_downloaded(model_name):
    return os.path.isdir(os.path.join(models_dir, model_name))

def download_model(model_name):
    repo_id = ALL_MODELS[model_name]
    token = st.secrets["huggingface"]["token"]  # 🔐 Load secret token
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = token  # Optional: set as env var
    with st.spinner(f"📥 Downloading {model_name}..."):
        snapshot_download(
            repo_id=repo_id,
            local_dir=os.path.join(models_dir, model_name),
            token=token,
            local_files_only=False
        )
        st.success(f"✅ {model_name} downloaded!")


if "selected_model" not in st.session_state:
    st.session_state.selected_model = "tiny.en"

st.markdown("### 🧠 Select Whisper Model")
cols = st.columns(len(ALL_MODELS))
for i, (name, _) in enumerate(ALL_MODELS.items()):
    if is_model_downloaded(name):
        if cols[i].button(f"✅ {name}", key=f"select_{name}"):
            st.session_state.selected_model = name
    else:
        if cols[i].button(f"📥 {name}", key=f"dl_{name}"):
            download_model(name)
            st.rerun()
st.markdown(f"**Current Model:** `{st.session_state.selected_model}`")
st.markdown("---")

# --------------------- SIDEBAR CONTROLS ---------------------
st.sidebar.header("Subtitle Customization")
with st.sidebar.expander("General Settings"):
    word_case = st.selectbox("Word Case", ["As Is", "UPPERCASE", "lowercase", "Title Case"])
    font_size = st.slider("Font Size", 20, 80, 48)
    y_position = st.slider("Vertical Position", 20, 200, 100)
    x_offset = st.slider("Horizontal Offset", -300, 300, 0)
    subtitle_area_width_percent = st.slider("Subtitle Width (%)", 50, 100, 80)

with st.sidebar.expander("Normal Style"):
    normal_font_color = st.color_picker("Text Color", "#FFFFFF")
    normal_opacity = st.slider("Opacity (%)", 0, 100, 100)
    bg_color = st.color_picker("Background", "#000000")
    bg_opacity = st.slider("BG Opacity (%)", 0, 100, 40)
    normal_outline_color = st.color_picker("Outline Color", "#000000")
    normal_outline_opacity = st.slider("Outline Opacity", 0, 100, 100)
    normal_outline_thickness = st.slider("Outline Thickness", 0, 10, 3)

with st.sidebar.expander("Active Word Style"):
    active_font_color = st.color_picker("Active Text Color", "#5096FF")
    active_opacity = st.slider("Active Opacity (%)", 0, 100, 100)
    size_scale = st.slider("Size Scale", 0.5, 2.0, 1.0, step=0.05)
    active_bg_color = st.color_picker("Active BG Color", "#5096FF")
    active_bg_opacity = st.slider("Active BG Opacity", 0, 100, 0)
    active_outline_color = st.color_picker("Active Border", "#000000")
    active_outline_opacity = st.slider("Active Outline Opacity", 0, 100, 100)
    active_outline_thickness = st.slider("Active Thickness", 0, 10, 3)

# --------------------- PREVIEW & FILE UPLOAD ---------------------
st.subheader("Live Subtitle Preview")
uploaded = st.file_uploader("Upload MP4 Video", type=["mp4"])
if uploaded: st.video(uploaded)

# --------------------- SESSION INIT ---------------------
for key, default in {
    "original_video_path": None,
    "original_transcript": None,
    "srt_content": "",
    "temp_dirs": [],
    "generated_video_path": None
}.items():
    st.session_state.setdefault(key, default)

def cleanup_temp_dirs():
    import shutil
    for d in st.session_state.temp_dirs:
        if os.path.exists(d): shutil.rmtree(d)
    st.session_state.temp_dirs = []

# --------------------- GENERATE VIDEO ---------------------
def generate_video(input_path, output_path, transcript, progress, log_area):
    logs = []
    def log(msg):
        logs.append(msg)
        log_area.text_area("Logs", "\n".join(logs[-20:]), height=150)

    try:
        render_subtitled_video(
            input_path, transcript, output_path,
            st_bar=progress, log_func=log,
            word_case=word_case,
            font_size=font_size,
            normal_font_color=normal_font_color,
            normal_font_opacity=normal_opacity,
            normal_border_color=normal_outline_color,
            normal_border_opacity=normal_outline_opacity,
            normal_border_thickness=normal_outline_thickness,
            active_font_color=active_font_color,
            active_font_opacity=active_opacity,
            active_word_size_scale=size_scale,
            active_word_bg_color=active_bg_color,
            active_word_bg_opacity=active_bg_opacity,
            active_border_color=active_outline_color,
            active_border_opacity=active_outline_opacity,
            active_border_thickness=active_outline_thickness,
            bg_color=bg_color,
            bg_opacity=bg_opacity,
            y_position=y_position,
            x_offset=x_offset,
            subtitle_area_width_percent=subtitle_area_width_percent
        )
        return True, output_path
    except Exception as e:
        log(f"ERROR: {e}")
        st.error(str(e))
        return False, None
    finally:
        progress.empty()
        log_area.text_area("Final Logs", "\n".join(logs[-20:]), height=150, disabled=True)

def handle_generation():
    if not uploaded:
        st.warning("Please upload a video.")
        return

    progress = st.progress(0)
    logs = st.empty()
    cleanup_temp_dirs()

    tmpdir = tempfile.mkdtemp()
    st.session_state.temp_dirs.append(tmpdir)
    in_path = os.path.join(tmpdir, "input.mp4")
    audio_path = os.path.join(tmpdir, "audio.wav")
    out_path = os.path.join(tmpdir, "output.mp4")
    model_path = os.path.join("models", st.session_state.selected_model)

    try:
        with open(in_path, "wb") as f: f.write(uploaded.read())
        st.session_state.original_video_path = in_path
        extract_audio(in_path, audio_path, log_func=lambda m: logs.text_area("Log", m))
        progress.progress(30)

        transcript = transcribe(audio_path, model_path, log_func=lambda m: logs.text_area("Log", m))
        st.session_state.original_transcript = transcript
        st.session_state.srt_content = to_srt(transcript)

        success, final_path = generate_video(in_path, out_path, transcript, progress, logs)
        if success:
            st.session_state.generated_video_path = final_path
            st.success("✅ Video generated.")
            st.write("---")

    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.session_state.generated_video_path = None

# --------------------- TRIGGER INITIAL GENERATION ---------------------
if uploaded and st.button("🎯 Generate Subtitled Video"):
    handle_generation()

# --------------------- SRT EDITOR ---------------------
if st.session_state.original_transcript:
    st.subheader("Edit Subtitles (SRT)")
    edited_srt = st.text_area("Edit below:", st.session_state.srt_content, height=300)

    if st.button("🔄 Regenerate with Edited SRT"):
        if edited_srt != st.session_state.srt_content:
            st.info("Regenerating...")
            progress = st.progress(0)
            logs = st.empty()

            tmpdir = tempfile.mkdtemp()
            st.session_state.temp_dirs.append(tmpdir)

            edited_transcript = from_srt(edited_srt, st.session_state.original_transcript)
            new_out_path = os.path.join(tmpdir, "regenerated_output.mp4")

            success, final_path = generate_video(
                st.session_state.original_video_path, new_out_path,
                edited_transcript, progress, logs
            )

            if success:
                st.session_state.generated_video_path = final_path
                st.success("✅ Regeneration complete.")
        else:
            st.warning("No changes detected.")

# --------------------- OUTPUT ---------------------
if st.session_state.generated_video_path:
    st.subheader("Final Video")
    st.video(st.session_state.generated_video_path)
    with open(st.session_state.generated_video_path, "rb") as f:
        st.download_button("💾 Download Video", f.read(), file_name=os.path.basename(st.session_state.generated_video_path))
