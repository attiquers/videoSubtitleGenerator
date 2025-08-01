import datetime

def _format_time(seconds):
    """Converts a time in seconds to an SRT-formatted time string."""
    td = datetime.timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def to_srt(transcript):
    """Converts a word-level transcript to an SRT string."""
    srt_content = ""
    for i, seg in enumerate(transcript):
        text = " ".join([word["word"] for word in seg["words"]]).strip()
        if not text:
            continue
        start_time = _format_time(seg["start"])
        end_time = _format_time(seg["end"])
        srt_content += f"{i + 1}\n"
        srt_content += f"{start_time} --> {end_time}\n"
        srt_content += f"{text}\n\n"
    return srt_content

def from_srt(srt_string, original_transcript):
    """
    Parses an SRT string and maps the new text back to the original transcript's timings.
    This maintains the original word-level timings as best as possible.
    """
    segments = srt_string.strip().split('\n\n')
    new_transcript = []
    
    original_segments = [seg for seg in original_transcript if "words" in seg]
    
    for i, segment_str in enumerate(segments):
        lines = segment_str.strip().split('\n')
        if len(lines) < 3:
            continue

        # Extract timing from SRT line
        times_line = lines[1]
        start_str, end_str = times_line.split(" --> ")
        
        # New text from the user
        new_text = " ".join(lines[2:]).strip()

        # Find the corresponding original segment to get the original word timings
        if i < len(original_segments):
            original_segment = original_segments[i]
            
            # Create a new segment with the original timings
            new_segment = {
                "start": original_segment["start"],
                "end": original_segment["end"],
                "words": []
            }
            
            new_words_list = new_text.split()
            original_words_list = [word["word"] for word in original_segment["words"]]
            
            # Map new words to original timings
            num_words = len(original_words_list)
            for j in range(num_words):
                original_word_data = original_segment["words"][j]
                
                # Use the new word if available, otherwise fallback
                new_word_text = new_words_list[j] if j < len(new_words_list) else original_word_data["word"]
                
                new_word_data = {
                    "word": new_word_text,
                    "start": original_word_data["start"],
                    "end": original_word_data["end"]
                }
                new_segment["words"].append(new_word_data)
            
            new_transcript.append(new_segment)
    
    return new_transcript