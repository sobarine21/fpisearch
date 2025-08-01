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
API_KEY = st.secrets["GOOGLE_API_KEY"]  # Your Google API key from Streamlit secrets
CX = st.secrets["GOOGLE_SEARCH_ENGINE_ID"]  # Your Google Custom Search Engine ID

# Initializing session state for detected matches
if 'detected_matches' not in st.session_state:
    st.session_state.detected_matches = []

# Custom CSS to style the page
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

# Streamlit UI for title and description
st.title("🔎 FPI Investor Email Finder")
st.markdown("""
Upload a CSV file with a column "Name" containing FPI investor names.  
For each name, we will search the web, find the most relevant website, extract email addresses, and let you download the results as CSV.
""")

# CSV upload UI
uploaded_file = st.file_uploader("Upload CSV file with a column 'Name':", type=["csv"])
fpi_names = None

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    if "Name" not in df.columns:
        st.error("CSV must have a column named 'Name'.")
    else:
        fpi_names = df["Name"].dropna().unique().tolist()
        st.success(f"Loaded {len(fpi_names)} investor names.")

# Email extraction util
def extract_emails_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    emails = set(re.findall(email_pattern, text))
    # Remove likely false-positives (e.g. images, scripts, css)
    cleaned = {e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif'))}
    # Remove prefixes/suffixes that are artifacts
    cleaned = {e.strip(".;,") for e in cleaned if len(e) > 6 and "." in e}
    return list(cleaned)

def get_best_website_for_name(name, service):
    # Use Google Custom Search API to get the best site for the investor
    try:
        response = service.cse().list(q=name, cx=CX, num=3).execute()
        candidates = []
        for result in response.get('items', []):
            url = result['link']
            snippet = result.get('snippet', "")
            # Prefer pages that actually mention email/contact
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
            emails = extract_emails_from_html(html)
            return emails
    except Exception:
        pass
    return []

# Main logic
if st.button("🔍 Find Emails for Uploaded FPI Investors") and fpi_names:
    with st.spinner('⏳ Processing investor names and searching for emails...'):
        service = build("customsearch", "v1", developerKey=API_KEY)
        results = []
        for name in fpi_names:
            website = get_best_website_for_name(name, service)
            emails = []
            if website:
                emails = crawl_and_get_emails(website)
            results.append({
                "Name": name,
                "Website": website or "Not found",
                "Emails": ", ".join(emails) if emails else "Not found"
            })
        output_df = pd.DataFrame(results)
        st.session_state.detected_matches = results

        st.success(f"Done! Found emails for {len(fpi_names)} investors.")

        # Show sample results
        st.dataframe(output_df)

        # Download as CSV
        csv_bytes = output_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Emails as CSV",
            data=csv_bytes,
            file_name="fpi_investor_emails.csv",
            mime="text/csv"
        )

        # Optional: Word cloud of email domains
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

# Add Self-hosting and Source Code section
st.markdown(
    """
    ### Self-Hosting
    If you want to self-host this application or download the source code, please visit:  
        👉 [Download Source Code](https://dhruvbansal8.gumroad.com/l/hhwbm?_gl=1*1hk16wi*_ga*MTQwNDE3ODM4My4xNzM0MzcyNTUw*_ga_6LJN6D94N6*MTc0MDU4NTEwMi4yNS4xLjE3NDA1ODY3NDMuMC4wLjA.)
    """
)
