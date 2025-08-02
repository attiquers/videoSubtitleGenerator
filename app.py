# app.py
import os
import tempfile
import streamlit as st
from huggingface_hub import snapshot_download
from PIL import Image, ImageDraw, ImageFont
import sys
import shutil

from subtitle_core import extract_audio, transcribe, render_subtitled_video, _wrap_text
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

# --------------------- SESSION STATE INITIALIZATION ---------------------
# Initialize all styling parameters in session state for persistence and programmatic updates
for key, default in {
    "word_case": "As Is",
    "font_size": 48,
    "y_position_percent": 80,
    "x_offset": 0,
    "subtitle_area_width_percent": 80,
    "normal_font_color": "#FFFFFF",
    "normal_opacity": 100,
    "bg_color": "#000000",
    "bg_opacity": 0,
    "bg_border_radius": 0,
    "normal_outline_color": "#000000",
    "normal_outline_opacity": 100,
    "normal_outline_thickness": 3,
    "active_font_color": "#5096FF",
    "active_opacity": 100,
    "size_scale": 1.0,
    "active_bg_color": "#34DD00",
    "active_bg_opacity": 90,
    "active_bg_border_radius": 10,
    "active_outline_color": "#000000",
    "active_outline_opacity": 100,
    "active_outline_thickness": 3,
    "disable_active_style": False,
    "original_video_path": None,
    "original_transcript": None,
    "srt_content": "",
    "temp_dirs": [],
    "generated_video_path": None,
    "uploaded_video": None, # Add a key for the uploaded video object
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --------------------- SIDEBAR CONTROLS ---------------------
st.sidebar.header("Subtitle Customization")
with st.sidebar.expander("General Settings"):
    st.session_state.word_case = st.selectbox("Word Case", ["As Is", "UPPERCASE", "lowercase", "Title Case"], index=["As Is", "UPPERCASE", "lowercase", "Title Case"].index(st.session_state.word_case))
    st.session_state.font_size = st.slider("Font Size (px)", 20, 100, value=st.session_state.font_size, key="font_size_slider")
    st.session_state.y_position_percent = st.slider("Vertical Position (%)", 0, 100, value=st.session_state.y_position_percent, key="y_position_slider")
    st.session_state.x_offset = st.slider("Horizontal Offset", -300, 300, value=st.session_state.x_offset, key="x_offset_slider")
    st.session_state.subtitle_area_width_percent = st.slider("Subtitle Width (%)", 50, 100, value=st.session_state.subtitle_area_width_percent, key="subtitle_width_slider")

with st.sidebar.expander("Normal Style"):
    st.session_state.normal_font_color = st.color_picker("Text Color", st.session_state.normal_font_color, key="normal_color_picker")
    st.session_state.normal_opacity = st.slider("Opacity (%)", 0, 100, value=st.session_state.normal_opacity, key="normal_opacity_slider")
    st.session_state.bg_color = st.color_picker("Background", st.session_state.bg_color, key="bg_color_picker")
    st.session_state.bg_opacity = st.slider("BG Opacity (%)", 0, 100, value=st.session_state.bg_opacity, key="bg_opacity_slider")
    st.session_state.bg_border_radius = st.slider("BG Border Radius (px)", 0, 50, value=st.session_state.bg_border_radius, key="bg_radius_slider")
    st.session_state.normal_outline_color = st.color_picker("Outline Color", st.session_state.normal_outline_color, key="normal_outline_color_picker")
    st.session_state.normal_outline_opacity = st.slider("Outline Opacity", 0, 100, value=st.session_state.normal_outline_opacity, key="normal_outline_opacity_slider")
    st.session_state.normal_outline_thickness = st.slider("Outline Thickness", 0, 10, value=st.session_state.normal_outline_thickness, key="normal_outline_thickness_slider")

with st.sidebar.expander("Active Word Style"):
    st.session_state.disable_active_style = st.checkbox("Disable Active Style", value=st.session_state.disable_active_style)
    st.session_state.active_font_color = st.color_picker("Active Text Color", st.session_state.active_font_color, key="active_color_picker")
    st.session_state.active_opacity = st.slider("Active Opacity (%)", 0, 100, value=st.session_state.active_opacity, key="active_opacity_slider")
    st.session_state.size_scale = st.slider("Size Scale", 0.5, 2.0, value=st.session_state.size_scale, step=0.05, key="size_scale_slider")
    st.session_state.active_bg_color = st.color_picker("Active BG Color", st.session_state.active_bg_color, key="active_bg_color_picker")
    st.session_state.active_bg_opacity = st.slider("Active BG Opacity", 0, 100, value=st.session_state.active_bg_opacity, key="active_bg_opacity_slider")
    st.session_state.active_bg_border_radius = st.slider("Active BG Border Radius (px)", 0, 50, value=st.session_state.active_bg_border_radius, key="active_bg_radius_slider")
    st.session_state.active_outline_color = st.color_picker("Active Border", st.session_state.active_outline_color, key="active_outline_color_picker")
    st.session_state.active_outline_opacity = st.slider("Active Outline Opacity", 0, 100, value=st.session_state.active_outline_opacity, key="active_outline_opacity_slider")
    st.session_state.active_outline_thickness = st.slider("Active Thickness", 0, 10, value=st.session_state.active_outline_thickness, key="active_outline_thickness_slider")

# --------------------- RECOMMENDED STYLES BUTTONS ---------------------
st.markdown("---")
st.sidebar.header("Recommended Styles")
cols = st.sidebar.columns(2)

if cols[0].button("Vertical Style"):
    st.session_state.y_position_percent = 50
    st.session_state.word_case = "UPPERCASE"
    st.session_state.normal_font_color = "#FFFFFF"
    st.session_state.normal_outline_color = "#000000"
    st.session_state.normal_outline_thickness = 3
    st.session_state.bg_opacity = 0
    st.session_state.active_font_color = "#FFFFFF"
    st.session_state.active_outline_color = "#000000"
    st.session_state.active_outline_thickness = 3
    st.session_state.active_bg_color = "#FFFF00"  # Set active background color to yellow
    st.session_state.active_bg_opacity = 100     # Set active background opacity to 100
    st.session_state.size_scale = 1.0
    st.session_state.disable_active_style = False
    st.rerun()

if cols[1].button("Horizontal Style"):
    st.session_state.y_position_percent = 10
    st.session_state.word_case = "Title Case"
    st.session_state.normal_font_color = "#FFFF00"
    st.session_state.normal_outline_color = "#000000"
    st.session_state.normal_outline_thickness = 1
    st.session_state.bg_color = "#808080"
    st.session_state.bg_opacity = 50
    st.session_state.active_font_color = "#FFFF00"
    st.session_state.active_outline_color = "#000000"
    st.session_state.active_outline_thickness = 1
    st.session_state.active_bg_opacity = 0
    st.session_state.size_scale = 1.0
    st.session_state.disable_active_style = True
    st.rerun()

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

def generate_preview_image(width, height, subtitle_text, active_word_index, **kwargs):
    img = Image.new("RGB", (width, height), "black")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    font_path = get_font_path("Arial.ttf")
    font_size = kwargs.get("font_size", 48)

    normal_font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    active_font = ImageFont.truetype(font_path, int(font_size * kwargs['size_scale'])) if font_path else ImageFont.load_default()

    # Text wrapping logic for the preview
    max_subtitle_width_pixels = int(width * (kwargs['subtitle_area_width_percent'] / 100.0))
    words_data = [{"word": w, "start": 0, "end": 0} for w in subtitle_text.split()]

    # We use a dummy transcription format to leverage the wrapping function from subtitle_core
    wrapped_lines_data = _wrap_text(words_data, max_subtitle_width_pixels, normal_font, active_font, kwargs['word_case'], overlay_draw)

    line_height_estimate = normal_font.size * 1.2
    total_text_height = len(wrapped_lines_data) * line_height_estimate

    y_pos_pixels = height - int(height * (kwargs['y_position_percent'] / 100.0))
    y_pos_block_start = y_pos_pixels - (total_text_height // 2)

    # Calculate overall block width for background
    max_line_width = 0
    for line in wrapped_lines_data:
        line_width = sum(overlay_draw.textlength(apply_case(word['word'], kwargs['word_case']) + " ", font=normal_font) for word in line) - overlay_draw.textlength(" ", font=normal_font)
        if line_width > max_line_width:
            max_line_width = line_width

    x_pos_block_start = (width // 2 + kwargs['x_offset']) - (max_line_width // 2)

    padding = 10
    bg_rect_left = x_pos_block_start - padding
    bg_rect_right = x_pos_block_start + max_line_width + padding
    bg_rect_top = y_pos_block_start - (0.5 * padding)
    bg_rect_bottom = y_pos_block_start + total_text_height + (1.5 * padding)

    bg_rgba = hex_to_rgba(kwargs['bg_color'], kwargs['bg_opacity'])
    if kwargs['bg_opacity'] > 0:
        draw_rounded_rectangle(overlay_draw, (bg_rect_left, bg_rect_top, bg_rect_right, bg_rect_bottom), kwargs['bg_border_radius'], fill=bg_rgba)

    current_line_y = y_pos_block_start + padding
    word_counter = 0

    for line in wrapped_lines_data:
        line_width_for_centering = sum(overlay_draw.textlength(apply_case(word['word'], kwargs['word_case']) + " ", font=normal_font) for word in line) - overlay_draw.textlength(" ", font=normal_font)
        current_word_x = (width // 2 + kwargs['x_offset']) - (line_width_for_centering // 2)

        for word_data in line:
            is_active = (word_counter == active_word_index)
            rendered_word_text = apply_case(word_data['word'], kwargs['word_case'])

            # Conditionally apply active styles or fall back to normal
            if is_active and not kwargs.get('disable_active_style', False):
                word_font = active_font
                fill_color_rgba = hex_to_rgba(kwargs['active_font_color'], kwargs['active_opacity'])
                border_color_rgba = hex_to_rgba(kwargs['active_outline_color'], kwargs['active_outline_opacity'])
                border_thickness = kwargs['active_outline_thickness']
                if kwargs['active_bg_opacity'] > 0:
                    word_bbox = overlay_draw.textbbox((current_word_x, current_line_y), rendered_word_text, font=word_font)
                    space_width = (overlay_draw.textlength(" ", font=word_font)) * 0.5
                    bg_top = word_bbox[1] - space_width
                    bg_bottom = word_bbox[3] + space_width
                    bg_left = word_bbox[0] - space_width
                    bg_right = word_bbox[2] + space_width
                    draw_rounded_rectangle(overlay_draw, (bg_left, bg_top, bg_right, bg_bottom), kwargs['active_bg_border_radius'], fill=hex_to_rgba(kwargs['active_bg_color'], kwargs['active_bg_opacity']))
            else:
                word_font = normal_font
                fill_color_rgba = hex_to_rgba(kwargs['normal_font_color'], kwargs['normal_opacity'])
                border_color_rgba = hex_to_rgba(kwargs['normal_outline_color'], kwargs['normal_outline_opacity'])
                border_thickness = kwargs['normal_outline_thickness']


            if border_thickness > 0:
                for x_offset_outline in range(-border_thickness, border_thickness + 1):
                    for y_offset_outline in range(-border_thickness, border_thickness + 1):
                        if x_offset_outline != 0 or y_offset_outline != 0:
                            overlay_draw.text(
                                (current_word_x + x_offset_outline, current_line_y + y_offset_outline),
                                rendered_word_text,
                                font=word_font,
                                fill=border_color_rgba
                            )

            overlay_draw.text(
                (current_word_x, current_line_y),
                rendered_word_text,
                font=word_font,
                fill=fill_color_rgba
            )
            current_word_x += overlay_draw.textlength(rendered_word_text + " ", font=word_font)
            word_counter += 1

        current_line_y += line_height_estimate

    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    return img.convert("RGB")


st.subheader("Live Subtitle Preview")
st.markdown("This shows a sample of how your subtitles will look. Change the **Subtitle Width** to see the text wrap automatically.")

preview_cols = st.columns(2)
with preview_cols[0]:
    st.markdown("#### Horizontal Video Preview")
    preview_h_params = {
        "word_case": st.session_state.word_case, "y_position_percent": st.session_state.y_position_percent, "x_offset": st.session_state.x_offset,
        "subtitle_area_width_percent": st.session_state.subtitle_area_width_percent, "font_size": st.session_state.font_size/2,
        "normal_font_color": st.session_state.normal_font_color, "normal_opacity": st.session_state.normal_opacity, "bg_color": st.session_state.bg_color,
        "bg_opacity": st.session_state.bg_opacity, "bg_border_radius": st.session_state.bg_border_radius, "normal_outline_color": st.session_state.normal_outline_color,
        "normal_outline_opacity": st.session_state.normal_outline_opacity, "normal_outline_thickness": st.session_state.normal_outline_thickness,
        "active_font_color": st.session_state.active_font_color, "active_opacity": st.session_state.active_opacity, "size_scale": st.session_state.size_scale,
        "active_bg_color": st.session_state.active_bg_color, "active_bg_opacity": st.session_state.active_bg_opacity,
        "active_bg_border_radius": st.session_state.active_bg_border_radius, "active_outline_color": st.session_state.active_outline_color,
        "active_outline_opacity": st.session_state.active_outline_opacity, "active_outline_thickness": st.session_state.active_outline_thickness,
        "disable_active_style": st.session_state.disable_active_style,
    }

    preview_horizontal = generate_preview_image(640, 360, "This is a sample subtitle line meow meow.", 3, **preview_h_params)
    st.image(preview_horizontal, use_column_width=True)

with preview_cols[1]:
    st.markdown("#### Vertical Video Preview")
    preview_v_params = {
        "word_case": st.session_state.word_case, "y_position_percent": st.session_state.y_position_percent, "x_offset": st.session_state.x_offset,
        "subtitle_area_width_percent": st.session_state.subtitle_area_width_percent, "font_size": st.session_state.font_size/3,
        "normal_font_color": st.session_state.normal_font_color, "normal_opacity": st.session_state.normal_opacity, "bg_color": st.session_state.bg_color,
        "bg_opacity": st.session_state.bg_opacity, "bg_border_radius": st.session_state.bg_border_radius, "normal_outline_color": st.session_state.normal_outline_color,
        "normal_outline_opacity": st.session_state.normal_outline_opacity, "normal_outline_thickness": st.session_state.normal_outline_thickness,
        "active_font_color": st.session_state.active_font_color, "active_opacity": st.session_state.active_opacity, "size_scale": st.session_state.size_scale,
        "active_bg_color": st.session_state.active_bg_color, "active_bg_opacity": st.session_state.active_bg_opacity,
        "active_bg_border_radius": st.session_state.active_bg_border_radius, "active_outline_color": st.session_state.active_outline_color,
        "active_outline_opacity": st.session_state.active_outline_opacity, "active_outline_thickness": st.session_state.active_outline_thickness,
        "disable_active_style": st.session_state.disable_active_style,
    }
    preview_vertical = generate_preview_image(360, 640, "This is a sample subtitle line meow meow.", 3, **preview_v_params)
    st.image(preview_vertical, use_column_width=True)


uploaded = st.file_uploader("Upload MP4 Video", type=["mp4"])
# Store the uploaded video object in session state
if uploaded:
    st.session_state.uploaded_video = uploaded
    st.video(uploaded)
# Display the video from the session state if it exists
elif "uploaded_video" in st.session_state and st.session_state.uploaded_video:
    st.video(st.session_state.uploaded_video)

# --------------------- SESSION INIT ---------------------
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
            word_case=st.session_state.word_case,
            font_size=st.session_state.font_size,
            normal_font_color=st.session_state.normal_font_color,
            normal_font_opacity=st.session_state.normal_opacity,
            normal_border_color=st.session_state.normal_outline_color,
            normal_border_opacity=st.session_state.normal_outline_opacity,
            normal_border_thickness=st.session_state.normal_outline_thickness,
            active_font_color=st.session_state.active_font_color,
            active_font_opacity=st.session_state.active_opacity,
            active_word_size_scale=st.session_state.size_scale,
            active_word_bg_color=st.session_state.active_bg_color,
            active_word_bg_opacity=st.session_state.active_bg_opacity,
            active_word_bg_border_radius=st.session_state.active_bg_border_radius,
            active_border_color=st.session_state.active_outline_color,
            active_border_opacity=st.session_state.active_outline_opacity,
            active_border_thickness=st.session_state.active_outline_thickness,
            bg_color=st.session_state.bg_color,
            bg_opacity=st.session_state.bg_opacity,
            bg_border_radius=st.session_state.bg_border_radius,
            y_position_percent=st.session_state.y_position_percent,
            x_offset=st.session_state.x_offset,
            subtitle_area_width_percent=st.session_state.subtitle_area_width_percent,
            disable_active_style=st.session_state.disable_active_style
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
    if not st.session_state.get("uploaded_video"):
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
        with open(in_path, "wb") as f: f.write(st.session_state.uploaded_video.read())
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
if st.session_state.get("uploaded_video") and st.button("🎯 Generate Subtitled Video"):
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