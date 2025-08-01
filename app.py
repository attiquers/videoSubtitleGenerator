import streamlit as st
import tempfile, os
from subtitle_core import extract_audio, transcribe, render_subtitled_video
from srt_tools import to_srt, from_srt

st.set_page_config(layout="wide")




##############################################################################################################
from huggingface_hub import snapshot_download

# --- Whisper Model Selector ---
ALL_MODELS = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base.en": "Systran/faster-whisper-base.en",
    "small.en": "Systran/faster-whisper-small.en",
    "medium.en": "Systran/faster-whisper-medium.en",
}

models_dir = "models"
os.makedirs(models_dir, exist_ok=True)

def is_model_downloaded(model_name):
    return os.path.isdir(os.path.join(models_dir, model_name))

def download_model(model_name):
    repo_id = ALL_MODELS[model_name]
    with st.spinner(f"📥 Downloading {model_name}..."):
        snapshot_download(repo_id, local_dir=os.path.join(models_dir, model_name))
        st.success(f"✅ {model_name} downloaded!")

if "selected_model" not in st.session_state:
    st.session_state.selected_model = "medium.en"

st.markdown("### 🧠 Select Whisper Model")

cols = st.columns(len(ALL_MODELS))

for i, (model_name, _) in enumerate(ALL_MODELS.items()):
    if is_model_downloaded(model_name):
        if cols[i].button(f"✅ {model_name}", key=f"model_{model_name}"):
            st.session_state.selected_model = model_name
    else:
        if cols[i].button(f"📥 {model_name}", key=f"download_{model_name}"):
            download_model(model_name)
            st.rerun()

st.markdown(f"**Current Model:** `{st.session_state.selected_model}`")

st.markdown("---")



##############################################################################################################











st.title("🎬 AI Subtitle Generator")

# --- Subtitle Customization Options ---
st.sidebar.header("Subtitle Customization")

# --- General Settings Expander ---
with st.sidebar.expander("General Settings", expanded=False):
    word_case = st.selectbox(
        "Word Case",
        options=["As Is", "UPPERCASE", "lowercase", "Title Case"],
        key="word_case_selectbox"
    )
    font_size = st.slider("Font Size", min_value=20, max_value=80, value=48, key="font_size_slider")
    y_position = st.slider("Vertical Position (from bottom)", min_value=20, max_value=200, value=100, key="y_pos_slider")
    x_offset = st.slider("Horizontal Offset (from center)", min_value=-300, max_value=300, value=0, key="x_offset_slider")
    subtitle_area_width_percent = st.slider("Subtitle Area Width (%)", min_value=50, max_value=100, value=80, key="subtitle_area_width_slider")

# --- Normal Subtitle Style Expander ---
with st.sidebar.expander("Normal Subtitle Style", expanded=False):
    normal_font_color_hex = st.color_picker("Text Color (Normal)", value="#FFFFFF", key="normal_font_color_picker")
    normal_font_opacity = st.slider("Text Opacity (Normal) (%)", min_value=0, max_value=100, value=100, key="normal_font_opacity_slider")
    bg_color_hex = st.color_picker("Background Color (Overall)", value="#000000", key="bg_color_picker")
    bg_opacity = st.slider("Background Opacity (%)", min_value=0, max_value=100, value=40, key="bg_opacity_slider")
    normal_border_color_hex = st.color_picker("Outline Color (Normal Word)", value="#000000", key="normal_border_color_picker")
    normal_border_opacity = st.slider("Outline Opacity (Normal Word) (%)", min_value=0, max_value=100, value=100, key="normal_border_opacity_slider")
    normal_border_thickness = st.slider("Outline Thickness", min_value=0, max_value=10, value=3, key="normal_border_thickness_slider")
    if normal_border_thickness == 0:
        st.info("Set Normal Border Thickness to 0 to disable border.")

# --- Current Word (Active) Style Expander ---
with st.sidebar.expander("Current Word (Active) Style", expanded=False):
    active_font_color_hex = st.color_picker("Text Color", value="#5096FF", key="active_font_color_picker")
    active_font_opacity = st.slider("Text Opacity (%)", min_value=0, max_value=100, value=100, key="active_font_opacity_slider")
    active_word_size_scale = st.slider(
        "Word Size Scale",
        min_value=0.5, max_value=2.0, value=1.0, step=0.05,
        key="active_word_size_scale_slider"
    )
    active_word_bg_color_hex = st.color_picker("Background Color", value="#5096FF", key="active_word_bg_color_picker")
    active_word_bg_opacity = st.slider("Background Opacity (%)", min_value=0, max_value=100, value=0, key="active_word_bg_opacity_slider")
    active_border_color_hex = st.color_picker("Border Color", value="#000000", key="active_border_color_picker")
    active_border_opacity = st.slider("Border Opacity (%)", min_value=0, max_value=100, value=100, key="active_border_opacity_slider")
    active_border_thickness = st.slider("Border Thickness", min_value=0, max_value=10, value=3, key="active_border_thickness_slider")
    if active_border_thickness == 0:
        st.info("Set Active Border Thickness to 0 to disable active word border.")

st.markdown("---")

# --- Live Preview Section (Main Section) ---
st.subheader("Live Subtitle Preview")

preview_video_width = 800
preview_video_height = int(preview_video_width * 9 / 16)
sample_full_text = "This is a longer sample text for the live preview to demonstrate how the subtitle area width setting will affect line wrapping and word breaks."
sample_current_word = "wrapping"

def hex_to_rgba_css(hex_color, alpha_percent):
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    a = alpha_percent / 100.0
    return f"rgba({r}, {g}, {b}, {a})"

def get_text_shadow_css(color, thickness):
    shadow_css = ""
    if thickness > 0:
        shadow_parts = []
        for x in range(-thickness, thickness + 1):
            for y in range(-thickness, thickness + 1):
                if x != 0 or y != 0:
                    shadow_parts.append(f"{x}px {y}px 0 {color}")
        shadow_css = ", ".join(shadow_parts)
    return shadow_css

# Apply case change for preview
def apply_case_change(text, case_option):
    if case_option == "UPPERCASE":
        return text.upper()
    elif case_option == "lowercase":
        return text.lower()
    elif case_option == "Title Case":
        return text.title()
    else:
        return text

normal_font_rgba_css = hex_to_rgba_css(normal_font_color_hex, normal_font_opacity)
active_font_rgba_css = hex_to_rgba_css(active_font_color_hex, active_font_opacity)
bg_color_rgba_css = hex_to_rgba_css(bg_color_hex, bg_opacity)
active_word_bg_color_rgba_css = hex_to_rgba_css(active_word_bg_color_hex, active_word_bg_opacity)
normal_border_rgba_css = hex_to_rgba_css(normal_border_color_hex, normal_border_opacity)
active_border_rgba_css = hex_to_rgba_css(active_border_color_hex, active_border_opacity)

subtitle_block_padding = 10
max_width_for_preview_px = preview_video_width * (subtitle_area_width_percent / 100.0)

words_list = sample_full_text.split()
combined_sample_text_html_parts = []
normal_text_shadow_css = get_text_shadow_css(normal_border_rgba_css, normal_border_thickness)
active_text_shadow_css = get_text_shadow_css(active_border_rgba_css, active_border_thickness)

for word_token in words_list:
    # Apply case change to all words for the preview
    word_token_display = apply_case_change(word_token, word_case)
    
    if word_token.lower() == sample_current_word.lower():
        span_html = (
            f'<span style="'
            f'color: {active_font_rgba_css};'
            f'text-shadow: {active_text_shadow_css};'
            f'line-height: 1.2;'
            f'box-sizing: border-box;'
            f'font-size: {font_size * active_word_size_scale}px;'
            f'background-color: {active_word_bg_color_rgba_css if active_word_bg_opacity > 0 else "transparent"};'
            f'padding: 2px 5px;'
            f'border-radius: 4px;'
            f'">{word_token_display}</span>'
        )
        combined_sample_text_html_parts.append(span_html)
    else:
        span_html = (
            f'<span style="'
            f'color: {normal_font_rgba_css};'
            f'text-shadow: {normal_text_shadow_css};'
            f'line-height: 1.2;'
            f'box-sizing: border-box;'
            f'font-size: {font_size}px;'
            f'">{word_token_display}</span>'
        )
        combined_sample_text_html_parts.append(span_html)

combined_sample_text_html = " ".join(combined_sample_text_html_parts)

# Construct the full HTML for the subtitle block
subtitle_html = (
    f'<div style="'
    f'position: absolute;'
    f'bottom: {y_position - subtitle_block_padding}px;'
    f'left: 50%;'
    f'transform: translateX(calc(-50% + {x_offset}px));'
    f'text-align: center;'
    f'background-color: {bg_color_rgba_css};'
    f'padding: {subtitle_block_padding}px {subtitle_block_padding + 5}px;'
    f'border-radius: 8px;'
    f'box-shadow: 0 4px 8px rgba(0,0,0,0.3);'
    f'display: block;'
    f'width: fit-content;'
    f'max-width: {max_width_for_preview_px}px;'
    f'box-sizing: border-box;'
    f'word-wrap: break-word;'
    f'white-space: normal;'
    f'margin-left: auto;'
    f'margin-right: auto;'
    f'">'
    f'{combined_sample_text_html}'
    f'</div>'
)

# Construct the main video frame and embed the subtitle HTML
preview_html = (
    f'<div style="'
    f'position: relative;'
    f'width: {preview_video_width}px;'
    f'height: {preview_video_height}px;'
    f'border: 2px solid #666;'
    f'background-color: #1a1a1a;'
    f'overflow: hidden;'
    f'margin-bottom: 20px;'
    f'">'
    f'{subtitle_html}'
    f'</div>'
)

# Use st.markdown to render the final HTML
st.markdown(preview_html, unsafe_allow_html=True)

st.write(f"*(This preview demonstrates approximate sizing, placement, and coloring. The word-level border on the active word is an approximation in the preview; actual rendering is pixel-accurate in the video.)*")
st.markdown("---")

uploaded = st.file_uploader("Upload MP4 video", type=["mp4"])

# --- Display uploaded video immediately if it exists ---
if uploaded:
    st.video(uploaded)

# --- Session State Initialization ---
# This block ensures all session state variables are initialized before use.
if 'original_video_path' not in st.session_state:
    st.session_state.original_video_path = None
if 'original_transcript' not in st.session_state:
    st.session_state.original_transcript = None
if 'srt_content' not in st.session_state:
    st.session_state.srt_content = ""
if 'temp_dirs' not in st.session_state:
    st.session_state.temp_dirs = []
if 'generated_video_path' not in st.session_state:
    st.session_state.generated_video_path = None

def cleanup_temp_dirs():
    for d in st.session_state.temp_dirs:
        if os.path.exists(d):
            import shutil
            shutil.rmtree(d)
    st.session_state.temp_dirs = []

def generate_video(input_path, output_path, transcript_to_use, progress_bar, log_area):
    logs = []
    def log_func(msg):
        logs.append(msg)
        log_area.text_area("Logs", "\n".join(logs[-20:]), height=150)
    
    try:
        render_subtitled_video(
            input_path,
            transcript_to_use,
            output_path,
            st_bar=progress_bar,
            log_func=log_func,
            word_case=word_case,
            font_size=font_size,
            normal_font_color=normal_font_color_hex,
            normal_font_opacity=normal_font_opacity,
            normal_border_color=normal_border_color_hex,
            normal_border_opacity=normal_border_opacity,
            normal_border_thickness=normal_border_thickness,
            active_font_color=active_font_color_hex,
            active_font_opacity=active_font_opacity,
            active_word_size_scale=active_word_size_scale,
            active_word_bg_color=active_word_bg_color_hex,
            active_word_bg_opacity=active_word_bg_opacity,
            active_border_color=active_border_color_hex,
            active_border_opacity=active_border_opacity,
            active_border_thickness=active_border_thickness,
            bg_color=bg_color_hex,
            bg_opacity=bg_opacity,
            y_position=y_position,
            x_offset=x_offset,
            subtitle_area_width_percent=subtitle_area_width_percent
        )
        return True, output_path
    except Exception as e:
        log_func(f"ERROR: An error occurred during video rendering: {e}")
        st.error(f"An error occurred during video rendering: {e}")
        return False, None
    finally:
        progress_bar.empty()
        log_area.text_area("Final Logs", "\n".join(logs[-20:]), height=150, disabled=True)

# Moved the function definition here, before it is called.
def handle_initial_generation():
    if uploaded:
        progress = st.progress(0)
        log_placeholder = st.empty()
        
        cleanup_temp_dirs()
        tmpdir = tempfile.mkdtemp()
        st.session_state.temp_dirs.append(tmpdir)
        
        in_path = os.path.join(tmpdir, "input.mp4")
        audio_path = os.path.join(tmpdir, "audio.wav")
        out_path = os.path.join(tmpdir, "output.mp4")
        # model_path = "faster-whisper-medium.en"
        model_path = os.path.join("models", st.session_state.selected_model)

        
        logs = []
        def log_func(msg):
            logs.append(msg)
            log_placeholder.text_area("Logs", "\n".join(logs[-20:]), height=150)
        
        progress.progress(0)
        log_func("Starting video processing...")

        try:
            with open(in_path, "wb") as f:
                f.write(uploaded.read())
            st.session_state.original_video_path = in_path
            log_func("✔ Video saved to temporary file.")

            extract_audio(in_path, audio_path, log_func)
            progress.progress(30)

            transcript = transcribe(audio_path, model_path, log_func)
            st.session_state.original_transcript = transcript
            progress.progress(60)

            srt_content = to_srt(transcript)
            st.session_state.srt_content = srt_content
            
            success, final_video_path = generate_video(in_path, out_path, transcript, progress, log_placeholder)
            if success:
                st.session_state.generated_video_path = final_video_path
                st.success("✅ Initial video generation complete.")
                st.write("---")
                
        except Exception as e:
            st.error(f"An error occurred: {e}")
            log_func(f"ERROR: {e}")
            st.session_state.generated_video_path = None
        finally:
            progress.empty()
            log_placeholder.text_area("Final Logs", "\n".join(logs[-20:]), height=150, disabled=True)


if uploaded and st.button("🎯 Generate Subtitled Video (Initial)"):
    handle_initial_generation()


# --- SRT Editing and Regeneration ---
if st.session_state.original_transcript:
    st.subheader("Edit Subtitles (SRT)")
    edited_srt = st.text_area(
        "Make changes to the SRT text below:",
        st.session_state.srt_content,
        height=300
    )

    if st.button("🔄 Regenerate Video with Edited SRT"):
        if edited_srt != st.session_state.srt_content:
            st.info("Regenerating video with your edits...")
            
            regeneration_progress = st.progress(0)
            regeneration_log_placeholder = st.empty()
            
            try:
                tmpdir = tempfile.mkdtemp()
                st.session_state.temp_dirs.append(tmpdir)
                
                edited_transcript = from_srt(edited_srt, st.session_state.original_transcript)
                
                new_out_path = os.path.join(tmpdir, "regenerated_output.mp4")
                
                success, final_video_path = generate_video(st.session_state.original_video_path, new_out_path, edited_transcript, regeneration_progress, regeneration_log_placeholder)
                
                if success:
                    st.session_state.generated_video_path = final_video_path
                    st.success("✅ Regeneration complete.")
            except Exception as e:
                st.error(f"An error occurred during regeneration: {e}")
        else:
            st.warning("No changes detected in the SRT. Video not regenerated.")

# --- Consolidated Display and Download Section ---
# This section will always run and display the latest generated video
if st.session_state.generated_video_path:
    st.markdown("---")
    st.subheader("Final Subtitled Video")
    st.video(st.session_state.generated_video_path)
    
    # Provide a download button for the latest generated video
    with open(st.session_state.generated_video_path, "rb") as f:
        st.download_button(
            "💾 Download Subtitled Video",
            f.read(),
            file_name=os.path.basename(st.session_state.generated_video_path)
        )
