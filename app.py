# app.py
import os
import tempfile
import streamlit as st
from huggingface_hub import snapshot_download
from PIL import Image, ImageDraw, ImageFont
import sys
import shutil
import traceback

from subtitle_core import extract_audio, transcribe, render_subtitled_video, _wrap_text
from srt_tools import to_srt, from_srt

# --------------------- CONFIG ---------------------
st.set_page_config(layout="wide")
st.title("🎬 AI Subtitle Generator")
st.markdown("""
> ⚠️ **NOTE:** Recommended to install locally even without a GPU – it works faster and reliable.  
> 📹 [Watch local install guide](https://youtu.be/CH0YDqiCuoA)
""")

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
    
    # Remove the token-related code
    # token = st.secrets.get("huggingface", {}).get("token")
    # if not token:
    #     st.error("Hugging Face API token not found in Streamlit secrets.")
    #     return
    
    # os.environ["HUGGINGFACEHUB_API_TOKEN"] = token # This line is no longer needed
    
    with st.spinner(f"📥 Downloading {model_name}..."):
        try:
            # The 'token' parameter is no longer necessary for public models
            snapshot_download(
                repo_id=repo_id,
                local_dir=os.path.join(models_dir, model_name),
                local_files_only=False
            )
            st.success(f"✅ {model_name} downloaded!")
        except Exception as e:
            st.error(f"Failed to download model {model_name}: {e}")

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
for key, default in {
    "word_case": "As Is", "font_size": 48, "y_position_percent": 80,
    "x_offset": 0, "subtitle_area_width_percent": 80,
    "normal_font_color": "#FFF01C", "normal_opacity": 100,
    "bg_color": "#000000", "bg_opacity": 15, "bg_border_radius": 0,
    "normal_outline_color": "#000000", "normal_outline_opacity": 100,
    "normal_outline_thickness": 2,
    "active_font_color": "#5096FF", "active_opacity": 100, "size_scale": 1.0,
    "active_bg_color": "#34DD00", "active_bg_opacity": 90, "active_bg_border_radius": 10,
    "active_outline_color": "#000000", "active_outline_opacity": 100,
    "active_outline_thickness": 2, "disable_active_style": True,
    "original_video_path": None, "original_transcript": None,
    "srt_content": "", "temp_dirs": [], "generated_video_path": None,
    "uploaded_video": None, "selected_font": "Arial.ttf",
    "selected_style_key": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --------------------- FONT SELECTION ---------------------
font_files = [f for f in os.listdir("fonts") if f.endswith((".ttf", ".otf"))]
font_files.insert(0, "Arial.ttf")

try:
    font_index = font_files.index(st.session_state.selected_font)
except ValueError:
    font_index = 0

# --------------------- SIDEBAR CONTROLS ---------------------
st.sidebar.header("Subtitle Customization")
with st.sidebar.expander("General Settings"):
    st.session_state.word_case = st.selectbox(
        "Word Case",
        ["As Is", "UPPERCASE", "lowercase", "Title Case"],
        index=["As Is", "UPPERCASE", "lowercase", "Title Case"].index(st.session_state.word_case),
        key="word_case_selectbox"
    )
    st.session_state.selected_font = st.selectbox(
        "Font Style",
        font_files,
        index=font_index,
        key="font_style_selectbox"
    )
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

# Style 1
if "selected_style_key" in st.session_state and st.session_state.selected_style_key == "style1":
    with st.success("Selected"):
        st.sidebar.image(os.path.join("styles", "style1.png"), use_container_width=True)
else:
    st.sidebar.image(os.path.join("styles", "style1.png"), use_container_width=True)
if st.sidebar.button("Apply Style 1"):
    st.session_state.update({
        "selected_font": "Exo-Black.otf",
        "y_position_percent": 30,
        "word_case": "UPPERCASE", "normal_font_color": "#FFFF00",
        "normal_outline_color": "#000000", "normal_outline_thickness": 4,
        "bg_opacity": 0, "active_font_color": "#07D600",
        "active_outline_color": "#000000", "active_outline_thickness": 3,
        "active_bg_color": "#FFFF00", "active_bg_opacity": 0,
        "size_scale": 1.0, "disable_active_style": False,
        "selected_style_key": "style1"
    })
    st.rerun()

# Style 2
if "selected_style_key" in st.session_state and st.session_state.selected_style_key == "style2":
    with st.success("Selected"):
        st.sidebar.image(os.path.join("styles", "style2.png"), use_container_width=True)
else:
    st.sidebar.image(os.path.join("styles", "style2.png"), use_container_width=True)
if st.sidebar.button("Apply Style 2"):
    st.session_state.update({
        "selected_font": "Baloo-Regular.ttf",
        "y_position_percent": 30,
        "word_case": "UPPERCASE", "normal_font_color": "#FFFFFF",
        "normal_outline_color": "#000000", "normal_outline_thickness": 2,
        "bg_opacity": 0, "active_font_color": "#FFFFFF",
        "active_outline_color": "#000000", "active_outline_thickness": 2,
        "active_bg_color": "#961919", "active_bg_opacity": 100,
        "size_scale": 1.0, "disable_active_style": False,
        "selected_style_key": "style2"
    })
    st.rerun()

# Style 3
if "selected_style_key" in st.session_state and st.session_state.selected_style_key == "style3":
    with st.success("Selected"):
        st.sidebar.image(os.path.join("styles", "style3.png"), use_container_width=True)
else:
    st.sidebar.image(os.path.join("styles", "style3.png"), use_container_width=True)
if st.sidebar.button("Apply Style 3"):
    st.session_state.update({
        "selected_font": "AmaticSC-Regular.ttf",
        "font_size":52,
        "y_position_percent": 30,
        "word_case": "UPPERCASE", "normal_font_color": "#FFFFFF",
        "normal_outline_color": "#000000", "normal_outline_thickness": 2,
        "bg_opacity": 0, "active_font_color": "#961919",
        "active_outline_color": "#000000", "active_outline_thickness": 2,
        "active_bg_color": "#961919", "active_bg_opacity": 0,
        "size_scale": 0.85, "disable_active_style": False,
        "selected_style_key": "style3"
    })
    st.rerun()


# --------------------- LIVE PREVIEW ---------------------
def hex_to_rgba(hex_color, alpha_percent):
    hex_color = hex_color.lstrip('#')
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        a = int(255 * (alpha_percent / 100.0))
        return (r, g, b, a)
    except (ValueError, IndexError):
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

def get_font_path(font_name):
    local_font_path = os.path.join("fonts", font_name)
    if os.path.exists(local_font_path):
        return local_font_path
    
    system_font_paths = {
        "win32": os.path.join(os.environ.get("WINDIR", ""), "Fonts", font_name),
        "linux": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "darwin": "/Library/Fonts/Arial.ttf"
    }
    
    path = system_font_paths.get(sys.platform)
    return path if path and os.path.exists(path) else None

def apply_case(word_text, case_option):
    if case_option == "UPPERCASE": return word_text.upper()
    if case_option == "lowercase": return word_text.lower()
    if case_option == "Title Case": return word_text.title()
    return word_text

def generate_preview_image(width, height, subtitle_text, active_word_index, **kwargs):
    img = Image.new("RGB", (width, height), "white")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    font_path = get_font_path(kwargs.get("selected_font", "Arial.ttf"))
    font_size = kwargs.get("font_size", 48)

    try:
        normal_font = ImageFont.truetype(font_path, int(font_size))
        active_font = ImageFont.truetype(font_path, int(font_size * kwargs['size_scale']))
    except (IOError, TypeError):
        st.warning(f"Could not load font: {font_path}. Using default font.")
        normal_font = ImageFont.load_default()
        active_font = ImageFont.load_default()

    max_subtitle_width_pixels = int(width * (kwargs['subtitle_area_width_percent'] / 100.0))
    words_data = [{"word": w, "start": 0, "end": 0} for w in subtitle_text.split()]
    wrapped_lines_data = _wrap_text(words_data, max_subtitle_width_pixels, normal_font, kwargs['word_case'], overlay_draw)

    line_height_estimate = normal_font.size * 1.2
    total_text_height = len(wrapped_lines_data) * line_height_estimate
    y_pos_pixels = height - int(height * (kwargs['y_position_percent'] / 100.0))
    y_pos_block_start = y_pos_pixels - (total_text_height // 2)

    max_line_width = 0
    for line in wrapped_lines_data:
        line_width = sum(overlay_draw.textlength(apply_case(word['word'], kwargs['word_case']) + " ", font=normal_font) for word in line) - overlay_draw.textlength(" ", font=normal_font)
        if line_width > max_line_width:
            max_line_width = line_width

    x_pos_block_start = (width // 2 + kwargs['x_offset']) - (max_line_width // 2)
    padding = 10
    bg_rect = (x_pos_block_start - padding, y_pos_block_start - (0.5 * padding),
               x_pos_block_start + max_line_width + padding, y_pos_block_start + total_text_height + (1.75 * padding))

    if kwargs['bg_opacity'] > 0:
        draw_rounded_rectangle(overlay_draw, bg_rect, kwargs['bg_border_radius'], fill=hex_to_rgba(kwargs['bg_color'], kwargs['bg_opacity']))

    current_line_y = y_pos_block_start + padding
    word_counter = 0

    for line in wrapped_lines_data:
        line_width_for_centering = sum(overlay_draw.textlength(apply_case(word['word'], kwargs['word_case']) + " ", font=normal_font) for word in line) - overlay_draw.textlength(" ", font=normal_font)
        current_word_x = (width // 2 + kwargs['x_offset']) - (line_width_for_centering // 2)

        for word_data in line:
            is_active = (word_counter == active_word_index)
            rendered_word_text = apply_case(word_data['word'], kwargs['word_case'])
            word_font = active_font if is_active and not kwargs.get('disable_active_style') else normal_font
            
            fill_color_rgba = hex_to_rgba(kwargs['active_font_color'] if is_active and not kwargs.get('disable_active_style') else kwargs['normal_font_color'],
                                         kwargs['active_opacity'] if is_active and not kwargs.get('disable_active_style') else kwargs['normal_opacity'])
            
            border_color_rgba = hex_to_rgba(kwargs['active_outline_color'] if is_active and not kwargs.get('disable_active_style') else kwargs['normal_outline_color'],
                                            kwargs['active_outline_opacity'] if is_active and not kwargs.get('disable_active_style') else kwargs['normal_outline_opacity'])
            
            border_thickness = kwargs['active_outline_thickness'] if is_active and not kwargs.get('disable_active_style') else kwargs['normal_outline_thickness']

            if is_active and not kwargs.get('disable_active_style') and kwargs['active_bg_opacity'] > 0:
                word_bbox = overlay_draw.textbbox((current_word_x, current_line_y), rendered_word_text, font=word_font)
                space_width = (overlay_draw.textlength(" ", font=word_font)) * 0.5
                bg_rect_word = (word_bbox[0] - space_width, word_bbox[1] - space_width,
                                word_bbox[2] + space_width, word_bbox[3] + space_width)
                draw_rounded_rectangle(overlay_draw, bg_rect_word, kwargs['active_bg_border_radius'], fill=hex_to_rgba(kwargs['active_bg_color'], kwargs['active_bg_opacity']))

            if border_thickness > 0:
                for x_offset_outline in range(-border_thickness, border_thickness + 1):
                    for y_offset_outline in range(-border_thickness, border_thickness + 1):
                        if x_offset_outline != 0 or y_offset_outline != 0:
                            overlay_draw.text((current_word_x + x_offset_outline, current_line_y + y_offset_outline),
                                              rendered_word_text, font=word_font, fill=border_color_rgba)
            
            overlay_draw.text((current_word_x, current_line_y), rendered_word_text, font=word_font, fill=fill_color_rgba)
            current_word_x += overlay_draw.textlength(rendered_word_text + " ", font=word_font)
            word_counter += 1

        current_line_y += line_height_estimate

    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    return img.convert("RGB")

st.subheader("Live Subtitle Preview")
st.markdown("This shows a sample of how your subtitles will look. Change the **Subtitle Width** to see the text wrap automatically.")
preview_cols = st.columns([0.6, 0.4])
preview_h_params = {
    "word_case": st.session_state.word_case, "y_position_percent": st.session_state.y_position_percent, "x_offset": st.session_state.x_offset,
    "subtitle_area_width_percent": st.session_state.subtitle_area_width_percent, "font_size": st.session_state.font_size / 2,
    "normal_font_color": st.session_state.normal_font_color, "normal_opacity": st.session_state.normal_opacity, "bg_color": st.session_state.bg_color,
    "bg_opacity": st.session_state.bg_opacity, "bg_border_radius": st.session_state.bg_border_radius, "normal_outline_color": st.session_state.normal_outline_color,
    "normal_outline_opacity": st.session_state.normal_outline_opacity, "normal_outline_thickness": st.session_state.normal_outline_thickness,
    "active_font_color": st.session_state.active_font_color, "active_opacity": st.session_state.active_opacity, "size_scale": st.session_state.size_scale,
    "active_bg_color": st.session_state.active_bg_color, "active_bg_opacity": st.session_state.active_bg_opacity,
    "active_bg_border_radius": st.session_state.active_bg_border_radius, "active_outline_color": st.session_state.active_outline_color,
    "active_outline_opacity": st.session_state.active_outline_opacity, "active_outline_thickness": st.session_state.active_outline_thickness,
    "disable_active_style": st.session_state.disable_active_style, "selected_font": st.session_state.selected_font
}
# Define a common height for both images
common_height = 360
with preview_cols[0]:
    st.markdown("#### Horizontal Video Preview")
    # Generate horizontal image with 16:9 aspect ratio
    horizontal_width = int(common_height * (16 / 9)) # 640
    preview_horizontal = generate_preview_image(horizontal_width, common_height, "This is a sample subtitle line meow meow.", 3, **preview_h_params)
    st.image(preview_horizontal, use_container_width=True)

uploaded = st.file_uploader("Upload MP4 Video", type=["mp4"])
if uploaded:
    st.session_state.uploaded_video = uploaded
    st.video(uploaded)
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
            st_bar=progress, log_func=log, selected_font=st.session_state.selected_font,
            word_case=st.session_state.word_case, font_size=st.session_state.font_size,
            normal_font_color=st.session_state.normal_font_color, normal_font_opacity=st.session_state.normal_opacity,
            normal_border_color=st.session_state.normal_outline_color, normal_border_opacity=st.session_state.normal_outline_opacity,
            normal_border_thickness=st.session_state.normal_outline_thickness, active_font_color=st.session_state.active_font_color,
            active_font_opacity=st.session_state.active_opacity, active_word_size_scale=st.session_state.size_scale,
            active_word_bg_color=st.session_state.active_bg_color, active_word_bg_opacity=st.session_state.active_bg_opacity,
            active_word_bg_border_radius=st.session_state.active_bg_border_radius, active_border_color=st.session_state.active_outline_color,
            active_border_opacity=st.session_state.active_outline_opacity, active_border_thickness=st.session_state.active_outline_thickness,
            bg_color=st.session_state.bg_color, bg_opacity=st.session_state.bg_opacity,
            bg_border_radius=st.session_state.bg_border_radius, y_position_percent=st.session_state.y_position_percent,
            x_offset=st.session_state.x_offset, subtitle_area_width_percent=st.session_state.subtitle_area_width_percent,
            disable_active_style=st.session_state.disable_active_style
        )
        return True, output_path
    except Exception as e:
        log(f"ERROR: {e}")
        st.error(f"An error occurred: {e}")
        traceback.print_exc()
        return False, None
    finally:
        progress.empty()

def handle_generation():
    if not st.session_state.get("uploaded_video"):
        st.warning("Please upload a video.")
        return

    progress = st.progress(0)
    logs_area = st.empty()
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
        st.info("Extracting audio...")
        extract_audio(in_path, audio_path, log_func=lambda m: logs_area.text_area("Log", m, height=150))
        progress.progress(30)
        
        st.info("Transcribing audio...")
        transcript = transcribe(audio_path, model_path, log_func=lambda m: logs_area.text_area("Log", m, height=150))
        st.session_state.original_transcript = transcript
        st.session_state.srt_content = to_srt(transcript)
        
        st.info("Rendering video...")
        success, final_path = generate_video(in_path, out_path, transcript, progress, logs_area)
        
        if success:
            st.session_state.generated_video_path = final_path
            st.success("✅ Video generated!")
            st.write("---")
            logs_area.empty()
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.session_state.generated_video_path = None
        logs_area.text_area("Error Log", traceback.format_exc(), height=150)
    
if st.session_state.get("uploaded_video") and st.button("🎯 Generate Subtitled Video"):
    handle_generation()

# --------------------- SRT EDITOR ---------------------
if st.session_state.original_transcript:
    st.subheader("Edit Subtitles (SRT)")
    edited_srt = st.text_area("Edit below:", st.session_state.srt_content, height=300, key="srt_editor")

    if st.button("🔄 Regenerate with Edited SRT"):
        if edited_srt != st.session_state.srt_content:
            st.info("Regenerating...")
            progress = st.progress(0)
            logs_area = st.empty()

            tmpdir = tempfile.mkdtemp()
            st.session_state.temp_dirs.append(tmpdir)
            
            try:
                edited_transcript = from_srt(edited_srt, st.session_state.original_transcript)
                new_out_path = os.path.join(tmpdir, "regenerated_output.mp4")
                success, final_path = generate_video(st.session_state.original_video_path, new_out_path, edited_transcript, progress, logs_area)
                if success:
                    st.session_state.generated_video_path = final_path
                    st.success("✅ Regeneration complete.")
            except Exception as e:
                st.error(f"An error occurred during regeneration: {e}")
                logs_area.text_area("Error Log", traceback.format_exc(), height=150)
            finally:
                logs_area.empty()
        else:
            st.warning("No changes detected in SRT.")

# --------------------- OUTPUT ---------------------
if st.session_state.generated_video_path:
    st.subheader("Final Video")
    st.video(st.session_state.generated_video_path)
    with open(st.session_state.generated_video_path, "rb") as f:
        st.download_button("💾 Download Video", f.read(), file_name=os.path.basename(st.session_state.generated_video_path))