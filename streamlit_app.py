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

# Suppress XML parsing warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Set up the Google API keys and Custom Search Engine ID
API_KEY = st.secrets["GOOGLE_API_KEY"]
CX = st.secrets["GOOGLE_SEARCH_ENGINE_ID"]

# Initialize session state
if 'detected_matches' not in st.session_state:
    st.session_state.detected_matches = []

# Hide Streamlit default styles
hide_streamlit_style = """
    <style>
        .css-1r6p8d1 {display: none;}
        .css-1v3t3fg {display: none;}
        header {visibility: hidden;}
        .css-1tqja98 {visibility: hidden;}
        .stTextInput>div>div>input {background-color: #f0f0f5; border-radius: 10px;}
        .stButton>button {background-color: #5e35b1; color: white; border-radius: 10px; padding: 10px 20px;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Title and description
st.title("🔎 FPI Investor Email Finder")
st.markdown("""
Upload a CSV file with columns: `Name`, `Registration No.`, and `Address`.  
For each investor, we'll search the web, find the most relevant site, extract email addresses, and let you download the results.
""")

# Upload CSV file
uploaded_file = st.file_uploader("Upload CSV file with headers 'Name', 'Registration No.', 'Address':", type=["csv"])
df = None
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    required_cols = {"Name", "Registration No.", "Address"}
    if not required_cols.issubset(df.columns):
        st.error("CSV must have columns: 'Name', 'Registration No.', and 'Address'.")
        df = None
    else:
        st.success(f"Loaded {len(df)} investors.")

# Email extraction util
def extract_emails_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = set(re.findall(email_pattern, text))
    cleaned = {e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif'))}
    cleaned = {e.strip(".;,") for e in cleaned if len(e) > 6 and "." in e}
    return list(cleaned)

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

def crawl_and_get_emails(url):
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            html = resp.text
            return extract_emails_from_html(html)
    except Exception:
        pass
    return []

# Main logic
if st.button("🔍 Find Emails for Uploaded FPI Investors") and df is not None:
    with st.spinner('⏳ Searching for emails...'):
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

        st.success(f"Done! Processed {len(output_df)} investors.")
        st.dataframe(output_df)

        # Download CSV
        csv_bytes = output_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Emails as CSV",
            data=csv_bytes,
            file_name="fpi_investor_emails.csv",
            mime="text/csv"
        )

        # Word cloud
        all_emails = [email for row in results for email in row["Emails"].split(", ") if "@" in email]
        if all_emails:
            domains = [e.split("@")[1] for e in all_emails if "@" in e]
            domain_text = " ".join(domains)
            st.subheader("🌐 Word Cloud of Email Domains")
            wordcloud = WordCloud(width=800, height=300, background_color='white').generate(domain_text)
            plt.figure(figsize=(8, 3))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            st.pyplot(plt)

# Self-hosting info
st.markdown(
    """
    ### Self-Hosting
    Want to run this locally or on your server?  
    👉 [Download Source Code](https://dhruvbansal8.gumroad.com/l/hhwbm)
    """
)
