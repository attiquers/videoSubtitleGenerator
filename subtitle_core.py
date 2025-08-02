# subtitle_core.py
import numpy as np
from moviepy import VideoFileClip, VideoClip
from faster_whisper import WhisperModel
from PIL import ImageFont, ImageDraw, Image
from proglog import ProgressBarLogger
import os
import traceback
import sys
from functools import lru_cache

# --- Helper Functions ---

def draw_rounded_rectangle(draw_context, xy, radius, fill=None, outline=None):
    """Draws a rectangle with rounded corners using Pillow."""
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

class StreamlitLogger(ProgressBarLogger):
    """A custom logger for moviepy that updates a Streamlit progress bar."""
    def __init__(self, st_bar, log_func):
        super().__init__()
        self.st_bar = st_bar
        self.log = log_func
        self.prev_pct = -1

    def bars_callback(self, bar, attr, value, old_value=None):
        total = self.bars.get(bar, {}).get("total", 1)
        pct = int((value or 0) / total * 100)
        if pct != self.prev_pct:
            self.prev_pct = pct
            self.st_bar.progress(pct)

def hex_to_rgba(hex_color, alpha_percent):
    """Converts a hex color and alpha percentage to an RGBA tuple."""
    hex_color = hex_color.lstrip('#')
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = int(255 * (alpha_percent / 100.0))
        return (r, g, b, a)
    except ValueError:
        raise ValueError(f"Invalid hex color format: {hex_color}")

def apply_case(word_text, case_option):
    """Applies a specific case to a word."""
    if case_option == "UPPERCASE":
        return word_text.upper()
    elif case_option == "lowercase":
        return word_text.lower()
    elif case_option == "Title Case":
        return word_text.title()
    return word_text

@lru_cache(maxsize=32)
def get_font(log_func, font_name, font_size):
    """
    Finds and loads a font, caching the result.
    Prioritizes a local 'fonts' directory, then system fonts.
    """
    font_path = os.path.join("fonts", font_name)
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, font_size)

    # Fallback to system fonts
    if sys.platform == "win32":
        system_path = os.path.join(os.environ.get("WINDIR", ""), "Fonts", font_name)
        if os.path.exists(system_path):
            return ImageFont.truetype(system_path, font_size)
    elif sys.platform == "darwin":
        system_path = os.path.join("/Library/Fonts", font_name)
        if os.path.exists(system_path):
            return ImageFont.truetype(system_path, font_size)
    
    log_func(f"⚠️ Warning: Font '{font_name}' not found. Falling back to default.")
    return ImageFont.load_default(font_size)

def _wrap_text(words, max_width, font, word_case, draw_context):
    """
    Wraps a list of words into lines based on a max width.
    Returns a list of lines, where each line is a list of words.
    """
    lines = []
    current_line = []
    current_width = 0
    space_width = draw_context.textlength(" ", font=font)

    for word_data in words:
        word_text = apply_case(word_data["word"], word_case)
        word_width = draw_context.textlength(word_text, font=font)

        if current_line and (current_width + space_width + word_width > max_width):
            lines.append(current_line)
            current_line = [word_data]
            current_width = word_width
        else:
            if current_line:
                current_width += space_width
            current_line.append(word_data)
            current_width += word_width

    if current_line:
        lines.append(current_line)
    return lines

@lru_cache(maxsize=128)
def _get_text_layout(seg_tuple, max_width, font_name, font_size, word_case):
    """
    Pre-computes the layout for a subtitle segment to avoid recalculation.
    Using tuples for memoization cache key.
    """
    words = [{"word": w[0], "start": w[1], "end": w[2]} for w in seg_tuple]

    # Create temporary font and drawing context to calculate layout
    font = get_font(lambda x: None, font_name, font_size)
    temp_img = Image.new("RGBA", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    lines = _wrap_text(words, max_width, font, word_case, temp_draw)

    # Pre-calculate line widths and total height
    line_layouts = []
    line_height_estimate = font.size * 1.2
    total_text_height = len(lines) * line_height_estimate

    for line_words in lines:
        line_width = 0
        word_layouts = []
        for word_data in line_words:
            word_text = apply_case(word_data["word"], word_case)
            word_width = temp_draw.textlength(word_text, font=font)
            word_layouts.append({
                "word": word_data,
                "text": word_text,
                "width": word_width
            })
            line_width += word_width + temp_draw.textlength(" ", font=font)

        line_width -= temp_draw.textlength(" ", font=font) if line_words else 0
        line_layouts.append({"words": word_layouts, "width": line_width})

    return line_layouts, total_text_height

# --- Core Functions ---

def extract_audio(video_path, audio_path, log_func):
    """Extracts the audio from a video file and saves it as a WAV."""
    log_func("🔊 Extracting audio…")
    try:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(audio_path, codec="pcm_s16le", fps=16000)
        clip.close()
        log_func("✓ Audio extracted.")
    except Exception as e:
        log_func(f"ERROR: Failed to extract audio: {e}")
        raise

def transcribe(audio_path, model_path, log_func):
    """Transcribes an audio file using a Whisper model and returns word-level timestamps."""
    log_func("🧠 Transcribing audio… This may take a while for longer videos.")
    try:
        model = WhisperModel(model_path, compute_type="int8", local_files_only=True)
        segments, _ = model.transcribe(audio_path, word_timestamps=True)
        transcript = [
            {"start": seg.start, "end": seg.end,
             "words": [{"word": w.word, "start": w.start, "end": w.end}
                         for w in seg.words]}
            for seg in segments
        ]
        log_func(f"✓ Transcription complete ({len(transcript)} segments).")
        return transcript
    except Exception as e:
        log_func(f"ERROR: Failed to transcribe audio: {e}")
        traceback.print_exc()
        raise

def render_subtitled_video(
    input_path,
    transcript,
    output_path,
    st_bar,
    log_func,
    selected_font,  # Now a required parameter
    font_size=48,
    word_case="As Is",
    normal_font_color="#FFFFFF",
    normal_font_opacity=100,
    normal_border_color="#000000",
    normal_border_opacity=100,
    normal_border_thickness=0,
    active_font_color="#5096FF",
    active_font_opacity=100,
    active_word_size_scale=1.0,
    active_word_bg_color="#5096FF",
    active_word_bg_opacity=30,
    active_word_bg_border_radius=0,
    active_border_color="#FFFF00",
    active_border_opacity=100,
    active_border_thickness=2,
    bg_color="#000000",
    bg_opacity=70,
    bg_border_radius=0,
    y_position_percent=80,
    x_offset=0,
    subtitle_area_width_percent=80,
    disable_active_style=False
):
    """Renders a video with dynamic subtitles based on transcription data."""
    log_func("🎞️ Rendering subtitles and embedding audio… This is the longest step.")
    try:
        clip = VideoFileClip(input_path)
        width, height = clip.size
        log_func(f"Video dimensions: {width}x{height}")

        normal_text_rgba = hex_to_rgba(normal_font_color, normal_font_opacity)
        normal_border_rgba = hex_to_rgba(normal_border_color, normal_border_opacity)

        if not disable_active_style:
            active_text_rgba = hex_to_rgba(active_font_color, active_font_opacity)
            active_border_rgba = hex_to_rgba(active_border_color, active_border_opacity)
            active_word_bg_rgba = hex_to_rgba(active_word_bg_color, active_word_bg_opacity)

        background_rgba = hex_to_rgba(bg_color, bg_opacity)

        normal_font = get_font(log_func, selected_font, font_size)
        active_font = get_font(log_func, selected_font, int(font_size * active_word_size_scale))

        max_subtitle_width_pixels = int(width * (subtitle_area_width_percent / 100.0))
        padding = 10
        line_height_estimate = normal_font.size * 1.2
        
        # Pre-process all segments once for performance using memoized function
        processed_segments = []
        for seg in transcript:
            seg_tuple = tuple((w["word"], w["start"], w["end"]) for w in seg["words"])
            line_layouts, total_height = _get_text_layout(
                seg_tuple, max_subtitle_width_pixels, selected_font, font_size, word_case
            )
            processed_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "lines": line_layouts,
                "total_height": total_height,
                "max_line_width": max(l["width"] for l in line_layouts) if line_layouts else 0
            })

        def make_frame(t):
            frame_array = clip.get_frame(t)
            img = Image.fromarray(frame_array).convert("RGBA")
            subtitle_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(subtitle_overlay)

            current_segment = next((seg for seg in processed_segments if seg["start"] <= t <= seg["end"]), None)

            if current_segment:
                total_text_height = current_segment["total_height"]
                max_line_width = current_segment["max_line_width"]

                x_pos_block_start = (width // 2 + x_offset) - (max_line_width // 2)
                y_pos_pixels = height - int(height * (y_position_percent / 100.0))
                y_pos_block_start = y_pos_pixels - (total_text_height // 2)

                bg_rect_left = x_pos_block_start - padding
                bg_rect_right = x_pos_block_start + max_line_width + padding
                bg_rect_top = y_pos_block_start - (0.5 * padding)
                bg_rect_bottom = y_pos_block_start + total_text_height + (1.5 * padding)

                if bg_opacity > 0:
                    draw_rounded_rectangle(overlay_draw, (bg_rect_left, bg_rect_top, bg_rect_right, bg_rect_bottom), bg_border_radius, fill=background_rgba)

                current_line_y = y_pos_block_start + padding
                for line in current_segment["lines"]:
                    current_word_x = (width // 2 + x_offset) - (line["width"] // 2)
                    for word_layout in line["words"]:
                        word_data = word_layout["word"]
                        rendered_word_text = word_layout["text"].strip()
                        is_active_word = (word_data["start"] <= t <= word_data["end"])

                        if is_active_word and not disable_active_style:
                            word_font = active_font
                            fill_color = active_text_rgba
                            border_color = active_border_rgba
                            border_thickness = active_border_thickness
                            if active_word_bg_opacity > 0:
                                word_bbox = overlay_draw.textbbox((current_word_x, current_line_y), rendered_word_text, font=word_font)
                                space_width = (overlay_draw.textlength(" ", font=word_font)) * 0.5
                                bg_top = word_bbox[1] - space_width
                                bg_bottom = word_bbox[3] + space_width
                                bg_left = word_bbox[0] - space_width
                                bg_right = word_bbox[2] + space_width
                                draw_rounded_rectangle(overlay_draw, (bg_left, bg_top, bg_right, bg_bottom), active_word_bg_border_radius, fill=active_word_bg_rgba)
                        else:
                            word_font = normal_font
                            fill_color = normal_text_rgba
                            border_color = normal_border_rgba
                            border_thickness = normal_border_thickness

                        if border_thickness > 0:
                            for x_offset_outline in range(-border_thickness, border_thickness + 1):
                                for y_offset_outline in range(-border_thickness, border_thickness + 1):
                                    if x_offset_outline != 0 or y_offset_outline != 0:
                                        overlay_draw.text((current_word_x + x_offset_outline, current_line_y + y_offset_outline), rendered_word_text, font=word_font, fill=border_color)

                        overlay_draw.text((current_word_x, current_line_y), rendered_word_text, font=word_font, fill=fill_color)
                        current_word_x += overlay_draw.textlength(rendered_word_text + " ", font=word_font)

                    current_line_y += line_height_estimate
                
                img = Image.alpha_composite(img, subtitle_overlay)
            return np.array(img.convert("RGB"))

        final_video_clip = VideoClip(make_frame, duration=clip.duration)
        final_clip = final_video_clip.with_audio(clip.audio)
        fps = getattr(clip, "fps", 24)
        logger = StreamlitLogger(st_bar, log_func)
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=fps,
            logger=logger,
        )
        clip.close()
        log_func("✅ Subtitled video rendered.")
    except Exception as e:
        log_func(f"ERROR: Failed to render subtitled video: {e}")
        traceback.print_exc()
        raise