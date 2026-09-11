import os
from groq import Groq
from fpdf import FPDF
from dotenv import load_dotenv
import arabic_reshaper
from bidi.algorithm import get_display

class AudioAgent:
    def __init__(self):
        """Initialise l'agent avec la clé API Groq"""
        load_dotenv()
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    def transcribe_audio(self, audio_file_path, language="en"):
        """Transcrit un fichier audio avec Groq Whisper"""
        with open(audio_file_path, "rb") as audio_file:
            transcription = self.client.audio.transcriptions.create(
                file=("audio.mp3", audio_file.read()),
                model="whisper-large-v3",
                language=language,
            )
        return transcription
    
    def process_with_gpt(self, transcript_text, choice, language="en"):
        """Traite le texte avec Groq LLaMA selon le choix (résumé ou explication)"""
        if language == "darija":
            prompt = (
                f"لخص هاد النص اللي مكتوب بالدارجة المغربية. كتب التلخيص بالعربية:\n{transcript_text}"
                if choice == "🔍 Summarize"
                else f"شرح بالتفصيل هاد النص اللي مكتوب بالدارجة المغربية. كتب الشرح بالعربية:\n{transcript_text}"
            )
            system_msg = "أنت مساعد خبير في النصوص والتفريغ الصوتي. النص المعطى مكتوب بالدارجة المغربية. أجب باللغة العربية."
        elif language == "ar":
            prompt = (
                f"لخص النص التالي باللغة العربية:\n{transcript_text}"
                if choice == "🔍 Summarize"
                else f"اشرح بالتفصيل النص التالي باللغة العربية:\n{transcript_text}"
            )
            system_msg = "أنت مساعد خبير في النصوص والتفريغ الصوتي. أجب دائماً باللغة العربية."
        else:
            prompt = (
                f"Summarize the following transcript:\n{transcript_text}"
                if choice == "🔍 Summarize"
                else f"Explain in detail the following transcript:\n{transcript_text}"
            )
            system_msg = "You are an expert transcription assistant."
        
        response = self.client.chat.completions.create(
            # llama-3.3-70b-versatile a été retiré du catalogue Groq.
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    
    def _create_pdf(self, text, output_path, is_arabic=False):
        """Crée un PDF avec support Unicode et arabe (RTL)"""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Use a Windows system font that supports Arabic
        font_path = "C:/Windows/Fonts/arial.ttf"
        if os.path.exists(font_path):
            pdf.add_font("ArialUni", "", font_path, uni=True)
            pdf.set_font("ArialUni", size=14 if is_arabic else 12)
        else:
            pdf.set_font("Arial", size=12)
        
        if is_arabic:
            # Reshape Arabic characters and apply RTL
            reshaped_text = arabic_reshaper.reshape(text)
            display_text = get_display(reshaped_text)
            pdf.multi_cell(0, 10, display_text, align="R")
        else:
            pdf.multi_cell(0, 10, text)
        
        pdf.output(output_path)
        return output_path
    
    def create_transcript_pdf(self, transcript_text, is_arabic=False):
        """Crée un PDF de la transcription"""
        return self._create_pdf(transcript_text, "transcript.pdf", is_arabic)
    
    def create_gpt_pdf(self, gpt_output, is_arabic=False):
        """Crée un PDF de la sortie AI"""
        return self._create_pdf(gpt_output, "gpt_output.pdf", is_arabic)