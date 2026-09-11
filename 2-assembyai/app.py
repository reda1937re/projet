import streamlit as st
from dotenv import load_dotenv
import os
from speech_to_text import AudioAgent

# Load environment variables
load_dotenv()

# Initialize agent
agent = AudioAgent()

# Streamlit UI
st.title("🎤 Speech to Text + AI Summary/Explanation")
st.caption("Powered by Groq (Whisper + LLaMA)")

# Language selection
lang = st.selectbox(
    "🌍 Choose audio language / اختر لغة الصوت",
    ["English", "العربية (Arabic)", "🇲🇦 الدارجة المغربية (Darija)"]
)
if "Darija" in lang:
    lang_code = "darija"
    whisper_lang = "ar"  # Whisper uses "ar" for all Arabic dialects
    is_arabic = True
elif "Arabic" in lang:
    lang_code = "ar"
    whisper_lang = "ar"
    is_arabic = True
else:
    lang_code = "en"
    whisper_lang = "en"
    is_arabic = False

uploaded_audio = st.file_uploader("Upload your audio file (.mp3, .wav)", type=["mp3", "wav"])
if uploaded_audio is not None:
    # Save temporary file
    with open("temp_audio_file", "wb") as f:
        f.write(uploaded_audio.getbuffer())
    
    # Transcription
    spinner_text = "🔊 جاري التفريغ الصوتي..." if is_arabic else "🔊 Transcribing with Whisper..."
    with st.spinner(spinner_text):
        try:
            transcript = agent.transcribe_audio("temp_audio_file", language=whisper_lang)
            transcript_text = transcript.text
        except Exception as e:
            transcript_text = None
            st.error(f"❌ Transcription failed: {e}")
    
    if transcript_text:
        st.success("✅ تم التفريغ بنجاح" if is_arabic else "✅ Transcription complete")
        st.text_area("📝 النص المفرّغ:" if is_arabic else "📝 Transcript:", transcript_text, height=200)
        
        # Export transcription to PDF
        btn_label = "📄 تحميل PDF للنص" if is_arabic else "📄 Download transcript PDF"
        if st.button(btn_label):
            pdf_path = agent.create_transcript_pdf(transcript_text, is_arabic=is_arabic)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "تحميل PDF" if is_arabic else "Download PDF",
                    f, file_name="transcript.pdf"
                )
        
        # AI choice
        options = ["🔍 Summarize", "📖 Explain in detail"]
        radio_label = "ماذا تريد من الذكاء الاصطناعي؟" if is_arabic else "What do you want the AI to do?"
        choice = st.radio(radio_label, options)
        
        run_label = "🚀 تشغيل AI" if is_arabic else "Run AI"
        if st.button(run_label):
            spinner_ai = "🤖 الذكاء الاصطناعي يفكر..." if is_arabic else "🤖 AI is thinking..."
            with st.spinner(spinner_ai):
                ai_output = agent.process_with_gpt(transcript_text, choice, language=lang_code)
            
            st.success("✅ الإجابة جاهزة" if is_arabic else "✅ AI response ready")
            st.text_area(
                "🤖 نتيجة الذكاء الاصطناعي:" if is_arabic else "🤖 AI Output:",
                ai_output, height=300
            )
            
            # Export AI result to PDF
            btn_ai_label = "📑 تحميل PDF للنتيجة" if is_arabic else "📑 Download AI Output PDF"
            if st.button(btn_ai_label):
                pdf_path = agent.create_gpt_pdf(ai_output, is_arabic=is_arabic)
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "تحميل PDF" if is_arabic else "Download AI Output PDF",
                        f, file_name="ai_output.pdf"
                    )