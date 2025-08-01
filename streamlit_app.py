import streamlit as st
import requests
from googleapiclient.discovery import build
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from langdetect import detect
import re
import pandas as pd
import matplotlib.pyplot as plt
import warnings
from wordcloud import WordCloud

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Load secrets
API_KEY = st.secrets["GOOGLE_API_KEY"]
CX = st.secrets["GOOGLE_SEARCH_ENGINE_ID"]

if 'detected_matches' not in st.session_state:
    st.session_state.detected_matches = []

# UI Styling
st.markdown("""
    <style>
        .css-1r6p8d1, .css-1v3t3fg, header, .css-1tqja98 {display: none;}
        .stTextInput>div>div>input {background-color: #f0f0f5; border-radius: 10px;}
        .stButton>button {background-color: #5e35b1; color: white; border-radius: 10px; padding: 10px 20px;}
    </style>
""", unsafe_allow_html=True)

st.title("🔎 FPI Investor Email Finder")
st.markdown("""
Upload an Excel file with the columns: **Name**, **Registration No.**, and **Address**.  
This tool finds relevant websites and extracts email addresses for FPI investors.
""")

# Excel uploader
uploaded_file = st.file_uploader("Upload Excel (.xlsx) file:", type=["xlsx"])
df = None

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        required_cols = {"Name", "Registration No.", "Address"}
        if not required_cols.issubset(df.columns):
            st.error("The Excel file must contain columns: Name, Registration No., and Address.")
            df = None
        else:
            st.success(f"Loaded {len(df)} investor records.")
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")

# Email extraction
def extract_emails_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = set(re.findall(email_pattern, text))
    cleaned = {e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif'))}
    cleaned = {e.strip(".;,") for e in cleaned if len(e) > 6 and "." in e}
    return list(cleaned)

# Get best site
def get_best_website_for_name(name, service):
    try:
        response = service.cse().list(q=name, cx=CX, num=3).execute()
        candidates = []
        for result in response.get('items', []):
            url = result['link']
            snippet = result.get('snippet', "")
            if "contact" in url.lower() or "email" in snippet.lower():
                return url
            candidates.append(url)
        if candidates:
            return candidates[0]
    except Exception:
        pass
    return None

# Crawl
def crawl_and_get_emails(url):
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            html = resp.text
            return extract_emails_from_html(html)
    except Exception:
        pass
    return []

# Run search
if st.button("🔍 Find Emails for Uploaded FPI Investors") and df is not None:
    with st.spinner('⏳ Searching web and extracting emails...'):
        service = build("customsearch", "v1", developerKey=API_KEY)
        results = []

        for idx, row in df.iterrows():
            name = row["Name"]
            reg_no = row["Registration No."]
            address = row["Address"]

            website = get_best_website_for_name(name, service)
            emails = crawl_and_get_emails(website) if website else []

            results.append({
                "Name": name,
                "Registration No.": reg_no,
                "Address": address,
                "Website": website or "Not found",
                "Emails": ", ".join(emails) if emails else "Not found"
            })

        output_df = pd.DataFrame(results)
        st.session_state.detected_matches = results

        st.success(f"✅ Completed. Found data for {len(output_df)} investors.")
        st.dataframe(output_df)

        # Download button
        csv_bytes = output_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv_bytes,
            file_name="fpi_investor_emails.csv",
            mime="text/csv"
        )

        # Word Cloud
        all_emails = [email for row in results for email in row["Emails"].split(", ") if "@" in email]
        if all_emails:
            domains = [e.split("@")[1] for e in all_emails]
            domain_text = " ".join(domains)
            st.subheader("🌐 Word Cloud of Email Domains")
            wordcloud = WordCloud(width=800, height=300, background_color='white').generate(domain_text)
            plt.figure(figsize=(8, 3))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            st.pyplot(plt)

# Self-hosting info
st.markdown("""
### Self-Hosting
To run this app locally or on your own server, visit:  
👉 [Download Source Code](https://dhruvbansal8.gumroad.com/l/hhwbm)
""")
