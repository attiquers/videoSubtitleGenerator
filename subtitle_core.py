import numpy as np
from moviepy import VideoFileClip, VideoClip, CompositeVideoClip
from faster_whisper import WhisperModel
from PIL import ImageFont, ImageDraw, Image
from proglog import ProgressBarLogger
import os
import traceback
import sys

class StreamlitLogger(ProgressBarLogger):
    def __init__(self, st_bar, log_func):
        super().__init__()
        self.st_bar = st_bar
        self.log = log_func
        self.prev_pct = -1

    def callback(self, **changes):
        return

    def bars_callback(self, bar, attr, value, old_value=None):
        total = self.bars.get(bar, {}).get("total", 1)
        pct = int((value or 0) / total * 100)
        if pct != self.prev_pct:
            self.prev_pct = pct
            self.st_bar.progress(pct)

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
        raise ValueError(f"Invalid hex color format: {hex_color}")

def extract_audio(video_path, audio_path, log_func):
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

def get_font_path(log_func, font_name="Arial.ttf"):
    """
    Finds and returns the path to a system font, trying common locations.
    """
    if sys.platform == "win32":
        try:
            return ImageFont.truetype(font_name)
        except OSError:
            log_func(f"Warning: {font_name} not found by Pillow. Trying system path.")
            font_path = os.path.join(os.environ["WINDIR"], "Fonts", font_name)
            if os.path.exists(font_path):
                return font_path
    elif sys.platform == "linux":
        linux_font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in linux_font_paths:
            if os.path.exists(path):
                return path
    elif sys.platform == "darwin":
        macos_font_paths = [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Arial.ttf",
        ]
        for path in macos_font_paths:
            if os.path.exists(path):
                return path

    log_func(f"ERROR: No suitable font found for the system. Falling back to default.")
    return None

def render_subtitled_video(
    input_path,
    transcript,
    output_path,
    st_bar,
    log_func,
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
    active_border_color="#FFFF00",
    active_border_opacity=100,
    active_border_thickness=2,
    bg_color="#000000",
    bg_opacity=70,
    y_position=100,
    x_offset=0,
    subtitle_area_width_percent=80
):
    log_func("🎞️ Rendering subtitles and embedding audio… This is the longest step.")
    try:
        clip = VideoFileClip(input_path)
        width, height = clip.size
        log_func(f"Video dimensions: {width}x{height}")

        normal_text_rgba = hex_to_rgba(normal_font_color, normal_font_opacity)
        normal_border_rgba = hex_to_rgba(normal_border_color, normal_border_opacity)
        active_text_rgba = hex_to_rgba(active_font_color, active_font_opacity)
        active_border_rgba = hex_to_rgba(active_border_color, active_border_opacity)
        active_word_bg_rgba = hex_to_rgba(active_word_bg_color, active_word_bg_opacity)
        background_rgba = hex_to_rgba(bg_color, bg_opacity)

        font_path = get_font_path(log_func, "Arial.ttf")
        
        normal_font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
        active_font = ImageFont.truetype(font_path, int(font_size * active_word_size_scale)) if font_path else ImageFont.load_default()
        
        log_func(f"Normal font size: {font_size}px")
        log_func(f"Active word font size: {int(font_size * active_word_size_scale)}px")
        
        max_subtitle_width_pixels = int(width * (subtitle_area_width_percent / 100.0))
        log_func(f"Max subtitle width: {max_subtitle_width_pixels}px ({subtitle_area_width_percent}%)")
        padding = 10

        def apply_case(word_text, case_option):
            if case_option == "UPPERCASE":
                return word_text.upper()
            elif case_option == "lowercase":
                return word_text.lower()
            elif case_option == "Title Case":
                return word_text.title()
            else:
                return word_text

        def make_frame(t):
            frame_array = clip.get_frame(t)
            img = Image.fromarray(frame_array).convert("RGBA")
            
            subtitle_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(subtitle_overlay)

            for seg in transcript:
                if seg["start"] <= t <= seg["end"]:
                    wrapped_lines_data = []
                    current_line_words_data = []
                    current_line_width = 0

                    try:
                        bbox_test = overlay_draw.textbbox((0, 0), "Tg", font=normal_font)
                        line_height_estimate = bbox_test[3] - bbox_test[1]
                        line_height_estimate = max(font_size * 1.2, line_height_estimate + 5)
                    except Exception:
                        line_height_estimate = font_size * 1.2

                    for word_data in seg["words"]:
                        # Apply case change to the word text before any other calculations
                        word_text = apply_case(word_data["word"], word_case)
                        is_active_word = (word_data["start"] <= t <= word_data["end"])
                        
                        word_font = active_font if is_active_word else normal_font
                        word_width = overlay_draw.textlength(word_text, font=word_font)
                        space_width = overlay_draw.textlength(" ", font=normal_font) if current_line_width else 0

                        if current_line_width and (current_line_width + space_width + word_width > max_subtitle_width_pixels):
                            wrapped_lines_data.append(current_line_words_data)
                            current_line_words_data = [word_data]
                            current_line_width = word_width
                        else:
                            if current_line_width:
                                current_line_width += space_width
                            
                            current_line_words_data.append(word_data)
                            current_line_width += word_width

                    if current_line_words_data:
                        wrapped_lines_data.append(current_line_words_data)
                        
                    actual_block_width = 0
                    for line_words_data in wrapped_lines_data:
                        line_width_actual = 0
                        for word_data in line_words_data:
                            word_text = apply_case(word_data["word"], word_case)
                            is_active_word = (word_data["start"] <= t <= word_data["end"])
                            word_font = active_font if is_active_word else normal_font
                            line_width_actual += overlay_draw.textlength(word_text, font=word_font)
                            line_width_actual += overlay_draw.textlength(" ", font=normal_font)
                        
                        line_width_actual -= overlay_draw.textlength(" ", font=normal_font)
                        
                        if line_width_actual > actual_block_width:
                            actual_block_width = line_width_actual
                    
                    total_text_height = len(wrapped_lines_data) * line_height_estimate
                    
                    x_pos_block_start = (width // 2 + x_offset) - (actual_block_width // 2)
                    y_pos_block_start = height - y_position - total_text_height
                    
                    bg_rect_left = x_pos_block_start - padding
                    bg_rect_top = y_pos_block_start - padding
                    bg_rect_right = x_pos_block_start + actual_block_width + padding
                    bg_rect_bottom = y_pos_block_start + total_text_height + padding

                    bg_rect_left = max(0, bg_rect_left)
                    bg_rect_top = max(0, bg_rect_top)
                    bg_rect_right = min(width, bg_rect_right)
                    bg_rect_bottom = min(height, bg_rect_bottom)

                    overlay_draw.rectangle(
                        (bg_rect_left, bg_rect_top, bg_rect_right, bg_rect_bottom),
                        fill=background_rgba
                    )

                    current_line_y = y_pos_block_start + padding
                    
                    for line_words_data in wrapped_lines_data:
                        line_width_for_centering = 0
                        for word_data in line_words_data:
                            word_text = apply_case(word_data["word"], word_case)
                            is_active_word = (word_data["start"] <= t <= word_data["end"])
                            word_font = active_font if is_active_word else normal_font
                            line_width_for_centering += overlay_draw.textlength(word_text + " ", font=word_font)
                        line_width_for_centering -= overlay_draw.textlength(" ", font=normal_font)
                        
                        current_word_x = (width // 2 + x_offset) - (line_width_for_centering // 2)
                        
                        for word_data_original in line_words_data:
                            word_text = word_data_original["word"]
                            is_active_word = (word_data_original["start"] <= t <= word_data_original["end"])

                            rendered_word_text = apply_case(word_text, word_case)
                            
                            word_font = active_font if is_active_word else normal_font
                            
                            fill_color = active_text_rgba if is_active_word else normal_text_rgba
                            border_color = active_border_rgba if is_active_word else normal_border_rgba
                            border_thickness = active_border_thickness if is_active_word else normal_border_thickness

                            # Only draw the active word background if opacity is > 0
                            if is_active_word and active_word_bg_opacity > 0:
                                word_bbox = overlay_draw.textbbox((current_word_x, current_line_y), rendered_word_text, font=word_font)
                                
                                active_word_padding_x = 3
                                active_word_padding_y = 6
                                
                                bg_left = word_bbox[0] - active_word_padding_x
                                bg_top = word_bbox[1] - active_word_padding_y
                                bg_right = word_bbox[2] + active_word_padding_x
                                bg_bottom = word_bbox[3] + active_word_padding_y
                                
                                overlay_draw.rectangle(
                                    (bg_left, bg_top, bg_right, bg_bottom),
                                    fill=active_word_bg_rgba
                                )
                            
                            if border_thickness > 0:
                                for x_offset_outline in range(-border_thickness, border_thickness + 1):
                                    for y_offset_outline in range(-border_thickness, border_thickness + 1):
                                        if x_offset_outline != 0 or y_offset_outline != 0:
                                            overlay_draw.text(
                                                (current_word_x + x_offset_outline, current_line_y + y_offset_outline),
                                                rendered_word_text,
                                                font=word_font,
                                                fill=border_color
                                            )
                            
                            overlay_draw.text(
                                (current_word_x, current_line_y),
                                rendered_word_text,
                                font=word_font,
                                fill=fill_color
                            )

                            current_word_x += overlay_draw.textlength(rendered_word_text + " ", font=word_font)

                        current_line_y += line_height_estimate

                    img = Image.alpha_composite(img, subtitle_overlay)
                    break
            
            return np.array(img)

        video_clip = VideoClip(make_frame, duration=clip.duration)
        final_clip = CompositeVideoClip([video_clip]).with_audio(clip.audio)
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