# app.py
import os
import tempfile
import streamlit as st
from huggingface_hub import snapshot_download
from PIL import Image, ImageDraw, ImageFont
import sys
import shutil

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
    token = st.secrets["huggingface"]["token"]
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = token
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
st.markdown("Using online or RAM > 6GB, and can wait 3x times more than `small.en`? Use `medium.en` for 95% subtitles' accuracy. Else choose `small.en` for subtitles' accuracy is about 80% ")
st.markdown("NOTE: Attaching retrieved subtitles with video will take the most of the time so, i suggest `medium.en` and go make tea while waiting :)")
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
    # Changed vertical position slider to a percentage-based 0-100 range
    y_position_percent = st.slider("Vertical Position (%)", 0, 100, 80)
    x_offset = st.slider("Horizontal Offset", -300, 300, 0)
    subtitle_area_width_percent = st.slider("Subtitle Width (%)", 50, 100, 80)

with st.sidebar.expander("Normal Style"):
    normal_font_color = st.color_picker("Text Color", "#FFFFFF")
    normal_opacity = st.slider("Opacity (%)", 0, 100, 100)
    bg_color = st.color_picker("Background", "#000000")
    bg_opacity = st.slider("BG Opacity (%)", 0, 100, 0)
    bg_border_radius = st.slider("BG Border Radius (px)", 0, 50, 0)
    normal_outline_color = st.color_picker("Outline Color", "#000000")
    normal_outline_opacity = st.slider("Outline Opacity", 0, 100, 100)
    normal_outline_thickness = st.slider("Outline Thickness", 0, 10, 3)

with st.sidebar.expander("Active Word Style"):
    active_font_color = st.color_picker("Active Text Color", "#5096FF")
    active_opacity = st.slider("Active Opacity (%)", 0, 100, 100)
    size_scale = st.slider("Size Scale", 0.5, 2.0, 1.0, step=0.05)
    active_bg_color = st.color_picker("Active BG Color", "#34DD00")
    active_bg_opacity = st.slider("Active BG Opacity", 0, 100, 90)
    active_bg_border_radius = st.slider("Active BG Border Radius (px)", 0, 50, 10)
    active_outline_color = st.color_picker("Active Border", "#000000")
    active_outline_opacity = st.slider("Active Outline Opacity", 0, 100, 100)
    active_outline_thickness = st.slider("Active Thickness", 0, 10, 3)

# --------------------- LIVE PREVIEW ---------------------
def hex_to_rgba(hex_color, alpha_percent):
    """Converts a hex color string and an alpha percentage to an RGBA tuple."""
    hex_color = hex_color.lstrip('#')
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = int(255 * (alpha_percent / 100.0))
        return (r, g, b, a)
    except ValueError:
        return (0, 0, 0, 0)

def draw_rounded_rectangle(draw_context, xy, radius, fill=None, outline=None):
    x0, y0, x1, y1 = xy
    max_radius = min((x1 - x0) / 2, (y1 - y0) / 2)
    radius = min(radius, max_radius)
    if radius <= 0:
        draw_context.rectangle(xy, fill=fill, outline=outline)
        return
    draw_context.rectangle([(x0 + radius, y0), (x1 - radius, y1)], fill=fill, outline=outline)
    draw_context.rectangle([(x0, y0 + radius), (x1, y1 - radius)], fill=fill, outline=outline)
    draw_context.pieslice([(x0, y0), (x0 + 2 * radius, y0 + 2 * radius)], 180, 270, fill=fill, outline=outline)
    draw_context.pieslice([(x1 - 2 * radius, y0), (x1, y0 + 2 * radius)], 270, 360, fill=fill, outline=outline)
    draw_context.pieslice([(x0, y1 - 2 * radius), (x0 + 2 * radius, y1)], 90, 180, fill=fill, outline=outline)
    draw_context.pieslice([(x1 - 2 * radius, y1 - 2 * radius), (x1, y1)], 0, 90, fill=fill, outline=outline)

def get_font_path(font_name="Arial.ttf"):
    """
    Finds and returns the path to a system font.
    """
    if sys.platform == "win32":
        font_path = os.path.join(os.environ.get("WINDIR", ""), "Fonts", font_name)
        if os.path.exists(font_path): return font_path
    elif sys.platform == "linux":
        linux_font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in linux_font_paths:
            if os.path.exists(path): return path
    elif sys.platform == "darwin":
        macos_font_paths = [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Arial.ttf",
        ]
        for path in macos_font_paths:
            if os.path.exists(path): return path
    return None

def apply_case(word_text, case_option):
    if case_option == "UPPERCASE":
        return word_text.upper()
    elif case_option == "lowercase":
        return word_text.lower()
    elif case_option == "Title Case":
        return word_text.title()
    else:
        return word_text

def calculate_font_size(draw, text, max_width, font_path, max_font_size=80):
    font_size = max_font_size
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    text_width = draw.textlength(text, font=font)
    while text_width > max_width and font_size > 10:
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        text_width = draw.textlength(text, font=font)
    return font_size

def generate_preview_image(width, height, subtitle_text, active_word_index, **kwargs):
    img = Image.new("RGB", (width, height), "black")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    font_path = get_font_path("Arial.ttf")
    
    max_subtitle_width_pixels = int(width * (kwargs['subtitle_area_width_percent'] / 100.0))
    font_size = calculate_font_size(overlay_draw, subtitle_text, max_subtitle_width_pixels, font_path)
    
    normal_font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    active_font = ImageFont.truetype(font_path, int(font_size * kwargs['size_scale'])) if font_path else ImageFont.load_default()
    
    words = subtitle_text.split()
    rendered_words = [apply_case(word, kwargs['word_case']) for word in words]
    
    total_line_width = sum(overlay_draw.textlength(word + " ", font=normal_font) for word in rendered_words) - overlay_draw.textlength(" ", font=normal_font)
    
    # Calculate y_pos based on percentage
    line_height = font_size * 1.2
    y_pos_pixels = height - int(height * (kwargs['y_position_percent'] / 100.0))
    y_pos = y_pos_pixels - (line_height // 2)
    
    x_pos = (width // 2 + kwargs['x_offset']) - (total_line_width // 2)
    
    # Background box dimensions
    bg_rect_left = x_pos - 10
    bg_rect_right = x_pos + total_line_width + 10
    bg_rect_top = y_pos - 5
    bg_rect_bottom = y_pos + line_height + 5
    
    bg_rgba = hex_to_rgba(kwargs['bg_color'], kwargs['bg_opacity'])
    if kwargs['bg_opacity'] > 0:
        draw_rounded_rectangle(overlay_draw, (bg_rect_left, bg_rect_top, bg_rect_right, bg_rect_bottom), kwargs['bg_border_radius'], fill=bg_rgba)
    
    current_word_x = x_pos
    
    for i, word in enumerate(rendered_words):
        is_active = (i == active_word_index)
        
        word_font = active_font if is_active else normal_font
        fill_color_rgba = hex_to_rgba(kwargs['active_font_color'], kwargs['active_opacity']) if is_active else hex_to_rgba(kwargs['normal_font_color'], kwargs['normal_opacity'])
        border_color_rgba = hex_to_rgba(kwargs['active_outline_color'], kwargs['active_outline_opacity']) if is_active else hex_to_rgba(kwargs['normal_outline_color'], kwargs['normal_outline_opacity'])
        border_thickness = kwargs['active_outline_thickness'] if is_active else kwargs['normal_outline_thickness']

        if is_active and kwargs['active_bg_opacity'] > 0:
            word_bbox = overlay_draw.textbbox((current_word_x, y_pos), word, font=word_font)
            bg_left = word_bbox[0] - 5
            bg_right = word_bbox[2] + 5
            bg_top = y_pos
            bg_bottom = y_pos + line_height
            active_bg_rgba = hex_to_rgba(kwargs['active_bg_color'], kwargs['active_bg_opacity'])
            draw_rounded_rectangle(overlay_draw, (bg_left, bg_top, bg_right, bg_bottom), kwargs['active_bg_border_radius'], fill=active_bg_rgba)
        
        if border_thickness > 0:
            for x_offset_outline in range(-border_thickness, border_thickness + 1):
                for y_offset_outline in range(-border_thickness, border_thickness + 1):
                    if x_offset_outline != 0 or y_offset_outline != 0:
                        overlay_draw.text(
                            (current_word_x + x_offset_outline, y_pos + y_offset_outline),
                            word,
                            font=word_font,
                            fill=border_color_rgba
                        )
        
        overlay_draw.text(
            (current_word_x, y_pos),
            word,
            font=word_font,
            fill=fill_color_rgba
        )
        current_word_x += overlay_draw.textlength(word + " ", font=word_font)
    
    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    return img.convert("RGB")

st.subheader("Live Subtitle Preview")
st.markdown("This shows a sample of how your subtitles will look.")

preview_cols = st.columns(2)
with preview_cols[0]:
    st.markdown("#### Horizontal Video Preview")
    preview_h_params = {
        "word_case": word_case, "y_position_percent": y_position_percent, "x_offset": x_offset,
        "subtitle_area_width_percent": subtitle_area_width_percent,
        "normal_font_color": normal_font_color, "normal_opacity": normal_opacity, "bg_color": bg_color,
        "bg_opacity": bg_opacity, "bg_border_radius": bg_border_radius, "normal_outline_color": normal_outline_color,
        "normal_outline_opacity": normal_outline_opacity, "normal_outline_thickness": normal_outline_thickness,
        "active_font_color": active_font_color, "active_opacity": active_opacity, "size_scale": size_scale,
        "active_bg_color": active_bg_color, "active_bg_opacity": active_bg_opacity,
        "active_bg_border_radius": active_bg_border_radius, "active_outline_color": active_outline_color,
        "active_outline_opacity": active_outline_opacity, "active_outline_thickness": active_outline_thickness,
    }
    
    preview_horizontal = generate_preview_image(640, 360, "This is a sample subtitle line", 2, **preview_h_params)
    st.image(preview_horizontal, use_column_width=True)

with preview_cols[1]:
    st.markdown("#### Vertical Video Preview")
    preview_v_params = {
        "word_case": word_case, "y_position_percent": y_position_percent, "x_offset": x_offset,
        "subtitle_area_width_percent": subtitle_area_width_percent,
        "normal_font_color": normal_font_color, "normal_opacity": normal_opacity, "bg_color": bg_color,
        "bg_opacity": bg_opacity, "bg_border_radius": bg_border_radius, "normal_outline_color": normal_outline_color,
        "normal_outline_opacity": normal_outline_opacity, "normal_outline_thickness": normal_outline_thickness,
        "active_font_color": active_font_color, "active_opacity": active_opacity, "size_scale": size_scale,
        "active_bg_color": active_bg_color, "active_bg_opacity": active_bg_opacity,
        "active_bg_border_radius": active_bg_border_radius, "active_outline_color": active_outline_color,
        "active_outline_opacity": active_outline_opacity, "active_outline_thickness": active_outline_thickness,
    }
    preview_vertical = generate_preview_image(360, 640, "This is a sample subtitle line", 2, **preview_v_params)
    st.image(preview_vertical, use_column_width=True)
    
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
            active_word_bg_border_radius=active_bg_border_radius,
            active_border_color=active_outline_color,
            active_border_opacity=active_outline_opacity,
            active_border_thickness=active_outline_thickness,
            bg_color=bg_color,
            bg_opacity=bg_opacity,
            bg_border_radius=bg_border_radius,
            y_position_percent=y_position_percent,
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