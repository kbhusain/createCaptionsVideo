import streamlit as st
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, CompositeAudioClip
from gtts import gTTS
import tempfile
import os

st.set_page_config(page_title="Local Video Captioner", layout="wide")

def process_video(video_path, text, font, font_size, color, placement, is_preview=False, crop_vertical=False, bg_music_path=None, bg_volume=0.2, add_tts=False):
    # Load video and enforce max 30 seconds
    clip = VideoFileClip(video_path)
    max_duration = min(clip.duration, 30.0)
    
    if is_preview:
        max_duration = min(max_duration, 5.0)
        
    clip = clip.subclipped(0, max_duration)
    
    # --- 9:16 Vertical Cropping ---
    if crop_vertical:
        target_ratio = 9 / 16
        current_ratio = clip.w / clip.h
        if current_ratio > target_ratio:
            new_width = clip.h * target_ratio
            clip = clip.cropped(
                x_center=clip.w / 2, 
                y_center=clip.h / 2, 
                width=new_width, 
                height=clip.h
            )

    # --- Generate TTS Audio FIRST ---
    tts_audio = None
    if add_tts and text.strip():
        tts_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts = gTTS(text=text, lang='en')
        tts.save(tts_temp.name)
        
        tts_audio = AudioFileClip(tts_temp.name)
        tts_duration = min(tts_audio.duration, max_duration)
        tts_audio = tts_audio.subclipped(0, tts_duration)
        
        # Use voice duration to pace the text chunks
        text_display_duration = tts_duration 
    else:
        text_display_duration = max_duration 

    # --- Process Text Chunks ---
    words = text.split()
    chunks = []
    current_chunk = ""
    
    for word in words:
        if len(current_chunk) + len(word) + 1 <= 20:
            current_chunk += (word + " ")
        else:
            chunks.append(current_chunk.strip())
            current_chunk = word + " "
    if current_chunk:
        chunks.append(current_chunk.strip())

    if chunks:
        time_per_chunk = text_display_duration / len(chunks)
        max_text_width = int(clip.w * 0.9) # 90% of screen width for margins
        
        text_clips = []
        for i, chunk in enumerate(chunks):
            txt_clip = TextClip(
                font=font, 
                text=chunk, 
                font_size=font_size, 
                color=color, 
                stroke_color="black", 
                stroke_width=3, 
                method='caption',            
                size=(max_text_width, None)  
            )
            
            if placement == "Top":
                pos = ('center', 50)
            elif placement == "Center":
                pos = 'center'
            else: # Bottom
                pos = ('center', clip.h - 100)
                
            txt_clip = txt_clip.with_position(pos).with_start(i * time_per_chunk).with_duration(time_per_chunk)
            text_clips.append(txt_clip)
            
        final_video = CompositeVideoClip([clip] + text_clips)
    else:
        final_video = clip

    # --- Master Audio Mixing ---
    audio_tracks = []
    
    if final_video.audio is not None:
        audio_tracks.append(final_video.audio)
        
    if bg_music_path:
        bg_audio = AudioFileClip(bg_music_path)
        bg_duration = min(bg_audio.duration, final_video.duration)
        bg_audio = bg_audio.subclipped(0, bg_duration).with_volume_scaled(bg_volume)
        audio_tracks.append(bg_audio)
        
    if tts_audio is not None:
        audio_tracks.append(tts_audio)
        
    if audio_tracks:
        mixed_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.with_audio(mixed_audio)
            
    return final_video

# --- UI Layout ---
st.title("Local Video Caption App")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Upload & Settings")
    uploaded_file = st.file_uploader("Upload Video", type=["mp4", "mov"])
    caption_text = st.text_area("Caption Text", "Type your captions here. They will be spoken and split automatically.")
    
    st.subheader("Caption Options")
    crop_for_reels = st.toggle("Crop to 9:16 (TikTok/Reels)", value=False)
    fnt_names= ["Ravie","BRITANIC", "Arial", "Courier", "Times-Roman", "POSTERABLE"]
    font_paths = {
        "Britanic": r"C:\Windows\Fonts\BRITANIC.ttf",
        "Ravie": r"C:\Windows\Fonts\ravie.ttf",
        "Courier": r"C:\Windows\Fonts\cour.ttf",
        "Times-Roman": r"C:\Windows\Fonts\times.ttf",
        "Verdana": r"C:\Windows\Fonts\verdana.ttf"
    }

    c1, c2 = st.columns(2)
    with c1:
        font_choice_name = st.selectbox("Font", list(font_paths.keys()))
        font_choice = font_paths[font_choice_name]
        font_size = st.slider("Font Size", 20, 100, 50)
    with c2:
        color_choice = st.color_picker("Text Color", "#FFFFFF")
        placement_choice = st.selectbox("Placement", ["Bottom", "Center", "Top"])

    st.subheader("Audio Settings")
    enable_tts = st.toggle("Generate AI Voiceover (Text-to-Speech)", value=True)
    uploaded_audio = st.file_uploader("Upload Background Music", type=["mp3"])
    music_volume = st.slider("Music Volume", min_value=0.01, max_value=1.0, value=0.2, step=0.05)

with col2:
    st.header("2. Preview & Output")
    video_placeholder = st.empty()
    download_placeholder = st.empty()
    
    if uploaded_file is not None:
        # Save uploaded video
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        tfile.write(uploaded_file.read())
        video_path = tfile.name
        
        # Save uploaded music
        bg_music_temp_path = None
        if uploaded_audio is not None:
            afile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            afile.write(uploaded_audio.read())
            bg_music_temp_path = afile.name

        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("Generate 5-Sec Preview"):
                with st.spinner("Generating preview..."):
                    preview_clip = process_video(
                        video_path, caption_text, font_choice, font_size, color_choice, placement_choice, 
                        is_preview=True, crop_vertical=crop_for_reels, bg_music_path=bg_music_temp_path, 
                        bg_volume=music_volume, add_tts=enable_tts
                    )
                    out_path = os.path.join(tempfile.gettempdir(), "preview_output.mp4")
                    preview_clip.write_videofile(out_path, codec="libx264", audio_codec="aac", fps=24, logger=None)
                    
                    video_placeholder.video(out_path)
                    st.success("Preview generated!")
                    
                    with open(out_path, "rb") as file:
                        download_placeholder.download_button("💾 Save Preview", file, "preview.mp4", "video/mp4", key="dl_preview")
                    
        with col_btn2:
            if st.button("Create Full Video"):
                with st.spinner("Generating full video..."):
                    final_clip = process_video(
                        video_path, caption_text, font_choice, font_size, color_choice, placement_choice, 
                        is_preview=False, crop_vertical=crop_for_reels, bg_music_path=bg_music_temp_path, 
                        bg_volume=music_volume, add_tts=enable_tts
                    )
                    final_out_path = os.path.join(tempfile.gettempdir(), "final_output.mp4")
                    final_clip.write_videofile(final_out_path, codec="libx264", audio_codec="aac", fps=24, logger=None)
                    
                    video_placeholder.video(final_out_path)
                    st.success("Full video generated!")
                    
                    with open(final_out_path, "rb") as file:
                        download_placeholder.download_button("💾 Save Final Video", file, "final.mp4", "video/mp4", key="dl_final")