import streamlit as st
import nltk
import spacy
import pandas as pd
import base64
import random
import time
import datetime
from pyresparser import ResumeParser
from pdfminer3.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter
import io
from streamlit_tags import st_tags
from PIL import Image
import pymysql
from pytube import YouTube
import plotly.express as px
import os

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# NLTK download
nltk.download('stopwords')

# Streamlit page setup
st.set_page_config(page_title="Smart Resume Analyzer", layout="wide")

theme = st.sidebar.radio("🌓 Select Theme", ["Light", "Dark"])
if theme == "Dark":
    st.markdown("""
        <style>
        .stApp { background-color: #1e1e1e; color: #f0f0f0; }
        h1, h2, h3, h4 { color: #ffffff; }
        .stButton>button { background-color: #444; color: white; }
        .stProgress > div > div > div > div { background-color: #00ccff; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .stApp { background-color: #ffffff; color: #000000; }
        h1, h2, h3, h4 { color: #1a1a1a; }
        .stButton>button { background-color: #0066cc; color: white; }
        .stProgress > div > div > div > div { background-color: #0073e6; }
        </style>
    """, unsafe_allow_html=True)
# === Local Resume Summary (spaCy 2.3.5) ===
def ai_resume_summary(resume_text):
    try:
        doc = nlp(resume_text)

        # Extract most informative sentences
        sentences = [sent.text.strip() for sent in doc.sents if 40 < len(sent.text.strip()) < 200]
        top_sentences = sentences[:4] if len(sentences) >= 4 else sentences

        # Format summary
        summary = "🔍 **Summary Based on Resume Content:**\n"
        for sent in top_sentences:
            summary += f"- {sent}\n"

        return summary
    except Exception as e:
        return f"⚠️ Local summary error: {e}"

# === Career Field Confidence Chart ===
def show_field_confidence(resume_skills):
    categories = {
        "Data Science": ['tensorflow', 'keras', 'pytorch', 'machine learning', 'deep learning'],
        "Web Development": ['react', 'django', 'php', 'laravel', 'html', 'css', 'javascript'],
        "Android": ['flutter', 'kotlin', 'android'],
        "iOS": ['swift', 'xcode', 'ios'],
        "UI/UX": ['figma', 'xd', 'ux', 'wireframe', 'prototyping']
    }

    scores = {}
    for field, keywords in categories.items():
        match_count = sum(1 for skill in resume_skills if skill.lower() in keywords)
        scores[field] = match_count

    fig = px.bar(
        x=list(scores.keys()),
        y=list(scores.values()),
        labels={'x': 'Career Field', 'y': 'Matched Skills'},
        title="Career Field Confidence Chart"
    )
    st.plotly_chart(fig)

# === Fixed Skill Match Radar Chart ===
def show_skill_radar(matched, missing):
    all_skills = list(dict.fromkeys(matched + missing))  # remove duplicates, preserve order
    values = [1 if skill in matched else 0 for skill in all_skills]

    if not all_skills:
        st.warning("⚠️ No skills to show on radar.")
        return

    fig = px.line_polar(
        r=values,
        theta=all_skills,
        line_close=True,
        title="Skill Match Radar Chart"
    )
    fig.update_traces(fill='toself')
    st.plotly_chart(fig)

# === PDF Reader ===
def pdf_reader(file_path):
    resource_manager = PDFResourceManager()
    output_string = io.StringIO()
    converter = TextConverter(resource_manager, output_string, laparams=LAParams())
    interpreter = PDFPageInterpreter(resource_manager, converter)
    with open(file_path, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            interpreter.process_page(page)
    converter.close()
    return output_string.getvalue()

def show_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)
def run():
    st.title("📄 Smart Resume Analyzer")
    st.sidebar.markdown("## Choose Role")
    choice = st.sidebar.selectbox("User Type", ["Normal User", "Admin"])

    img = Image.open('./Logo/SRA_Logo.jpg')
    img = img.resize((250, 250))
    st.image(img)

    if choice == 'Normal User':
        os.makedirs('Uploaded_Resumes', exist_ok=True)
        pdf_file = st.file_uploader("📎 Upload Your Resume (PDF)", type=["pdf"])
        if pdf_file:
            save_path = './Uploaded_Resumes/' + pdf_file.name
            with open(save_path, "wb") as f:
                f.write(pdf_file.getbuffer())
            show_pdf(save_path)

            resume_data = ResumeParser(save_path).get_extracted_data()
            if resume_data:
                resume_text = pdf_reader(save_path)

                # === Local AI Summary (spaCy) ===
                st.subheader("🧠 Resume Summary (Local NLP)")
                summary = ai_resume_summary(resume_text)
                st.markdown(summary)

                # === Basic Info ===
                st.subheader("📌 Basic Info")
                st.text("Name: " + resume_data.get('name', 'N/A'))
                st.text("Email: " + resume_data.get('email', 'N/A'))
                st.text("Contact: " + resume_data.get('mobile_number', 'N/A'))
                st.text("Pages: " + str(resume_data.get('no_of_pages', 'N/A')))

                # === Candidate Level ===
                pages = resume_data.get('no_of_pages', 0)
                cand_level = "Fresher" if pages == 1 else "Intermediate" if pages == 2 else "Experienced"
                st.success(f"📘 Candidate Level: {cand_level}")

                # === Skills Display ===
                st.subheader("💼 Extracted Skills")
                extracted_skills = resume_data.get('skills', [])
                st_tags(label="Your Skills", value=extracted_skills, key='skills')

                # === Field Confidence Chart ===
                st.subheader("📊 Career Field Confidence")
                show_field_confidence(extracted_skills)
                # === Field Detection & Course Recommendation ===
                from Courses import ds_course, web_course, android_course, ios_course, uiux_course, resume_videos, interview_videos

                reco_field, recommended_skills, rec_course = '', [], []
                ds_keywords = ['tensorflow', 'keras', 'pytorch', 'machine learning', 'deep learning']
                web_keywords = ['react', 'django', 'php', 'laravel', 'html', 'css']
                android_keywords = ['flutter', 'kotlin', 'android']
                ios_keywords = ['swift', 'xcode', 'ios']
                uiux_keywords = ['figma', 'xd', 'ux', 'wireframe']

                def course_recommender(course_list):
                    st.subheader("🎓 Recommended Courses")
                    rec_course = []
                    count = st.slider("Number of course recommendations:", 1, 10, 4)
                    random.shuffle(course_list)
                    for i, (name, link) in enumerate(course_list[:count]):
                        st.markdown(f"**{i+1}. [{name}]({link})**")
                        rec_course.append(name)
                    return rec_course

                for skill in extracted_skills:
                    skill = skill.lower()
                    if skill in ds_keywords:
                        reco_field = "Data Science"
                        recommended_skills = ['Keras', 'TensorFlow', 'Pandas']
                        rec_course = course_recommender(ds_course)
                        break
                    elif skill in web_keywords:
                        reco_field = "Web Development"
                        recommended_skills = ['React', 'Django', 'HTML', 'CSS']
                        rec_course = course_recommender(web_course)
                        break
                    elif skill in android_keywords:
                        reco_field = "Android Development"
                        recommended_skills = ['Flutter', 'Kotlin']
                        rec_course = course_recommender(android_course)
                        break
                    elif skill in ios_keywords:
                        reco_field = "iOS Development"
                        recommended_skills = ['Swift', 'Xcode']
                        rec_course = course_recommender(ios_course)
                        break
                    elif skill in uiux_keywords:
                        reco_field = "UI/UX Design"
                        recommended_skills = ['Figma', 'Adobe XD']
                        rec_course = course_recommender(uiux_course)
                        break

                # === Skill Match and Radar Chart ===
                st.subheader("🛠 Recommended Skills")
                st_tags(label="Suggested Skills", value=recommended_skills, key='rec_skills')

                matched_skills = [s for s in extracted_skills if s.lower() in [r.lower() for r in recommended_skills]]
                missing_skills = [s for s in recommended_skills if s.lower() not in [e.lower() for e in extracted_skills]]

                st.subheader("📈 Skill Match Radar")
                show_skill_radar(matched_skills, missing_skills)

                # === Resume Score and Tips ===
                st.subheader("📌 Resume Tips")
                resume_score = 0
                tips = {
                    "Objective": "career objective",
                    "Declaration": "declaration statement",
                    "Hobbies": "hobbies or interests",
                    "Achievements": "achievements section",
                    "Projects": "project details"
                }

                for key, label in tips.items():
                    if key.lower() in resume_text.lower():
                        resume_score += 20
                        st.success(f"[+] Found {label}")
                    else:
                        st.warning(f"[-] Missing {label}")

                st.subheader("📊 Resume Score")
                my_bar = st.progress(0)
                for i in range(resume_score):
                    my_bar.progress(i + 1)
                    time.sleep(0.01)
                st.success(f"✅ Resume Score: {resume_score} / 100")
                # === Save to Database ===
                def insert_data(name, email, res_score, timestamp, no_of_pages, reco_field, cand_level, skills, recommended_skills, courses):
                    connection = pymysql.connect(host='localhost', user='root', password='')
                    cursor = connection.cursor()
                    cursor.execute("CREATE DATABASE IF NOT EXISTS SRA;")
                    connection.select_db("sra")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS user_data (
                            ID INT NOT NULL AUTO_INCREMENT,
                            Name VARCHAR(100), Email_ID VARCHAR(50), resume_score VARCHAR(8),
                            Timestamp VARCHAR(50), Page_no VARCHAR(5), Predicted_Field VARCHAR(25),
                            User_level VARCHAR(30), Actual_skills VARCHAR(300),
                            Recommended_skills VARCHAR(300), Recommended_courses VARCHAR(600),
                            PRIMARY KEY (ID)
                        );
                    """)
                    sql = "INSERT INTO user_data VALUES (0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                    values = (name, email, res_score, timestamp, no_of_pages, reco_field,
                              cand_level, skills, recommended_skills, courses)
                    cursor.execute(sql, values)
                    connection.commit()
                    cursor.close()
                    connection.close()

                timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
                insert_data(
                    resume_data.get('name', ''),
                    resume_data.get('email', ''),
                    resume_score,
                    timestamp,
                    str(resume_data.get('no_of_pages', '')),
                    reco_field,
                    cand_level,
                    str(extracted_skills),
                    str(recommended_skills),
                    str(rec_course)
                )

                # === Bonus Videos ===
                st.subheader("🎬 Resume & Interview Preparation")
                st.video(random.choice(resume_videos))
                st.video(random.choice(interview_videos))

            else:
                st.error("❌ Could not extract resume data. Try another file.")

    else:
        # === Admin Panel ===
        st.header("🔐 Admin Panel")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login") and user == "project_main" and pwd == "mlhub123":
            connection = pymysql.connect(host='localhost', user='root', password='')
            connection.select_db("sra")
            df = pd.read_sql("SELECT * FROM user_data", connection)
            st.dataframe(df)

            # === CSV Export ===
            def get_table_download_link(df, filename, text):
                csv = df.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'

            st.markdown(get_table_download_link(df, "User_Data.csv", "📥 Download CSV"), unsafe_allow_html=True)

            st.subheader("📈 Field Distribution")
            st.plotly_chart(px.pie(df, names='Predicted_Field', title="Fields"))

            st.subheader("📊 Experience Levels")
            st.plotly_chart(px.pie(df, names='User_level', title="User Levels"))
        else:
            st.warning("👮 Enter correct admin credentials.")

# === Run the App ===
run()
