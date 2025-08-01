import streamlit as st
import requests
from googleapiclient.discovery import build
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import pandas as pd
import re
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import warnings
import time

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Load secrets
API_KEY = st.secrets["GOOGLE_API_KEY"]
CX = st.secrets["GOOGLE_SEARCH_ENGINE_ID"]

# UI Setup
st.title("🔎 Robust FPI Investor Email Finder")
st.markdown("""
Upload an Excel file (.xlsx) with **Name**, **Registration No.**, and **Address**.  
This version uses smarter Google search queries and parses even obfuscated emails like `contact [at] xyz.com`.
""")

uploaded_file = st.file_uploader("Upload Excel file:", type=["xlsx"])
df = None
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        required_cols = {"Name", "Registration No.", "Address"}
        if not required_cols.issubset(df.columns):
            st.error("File must contain: Name, Registration No., Address")
            df = None
        else:
            st.success(f"✅ Loaded {len(df)} records.")
    except Exception as e:
        st.error(f"❌ Error reading file: {e}")
        df = None

# Email extraction
def extract_emails_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")

    # Match regular & obfuscated emails
    regex = r'''(?:[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+|[a-zA-Z0-9_.+-]+\s?\[\s?at\s?\]\s?[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)'''
    raw_emails = re.findall(regex, text)

    cleaned_emails = []
    for e in raw_emails:
        e = e.replace(" [at] ", "@").replace("[at]", "@").replace(" ", "")
        e = e.strip(".,;:()[]<>")
        if "@" in e and not e.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.gif')):
            cleaned_emails.append(e)
    return list(set(cleaned_emails))

# Improved query
def get_best_website_for_name(name, service):
    query = f'"{name}" contact email site:.org OR site:.com'
    try:
        response = service.cse().list(q=query, cx=CX, num=3).execute()
        candidates = []
        for item in response.get("items", []):
            url = item["link"]
            snippet = item.get("snippet", "")
            if "contact" in url.lower() or "email" in snippet.lower():
                return url
            candidates.append(url)
        if candidates:
            return candidates[0]
    except Exception as e:
        return f"Error: {e}"
    return None

def crawl_and_get_emails(url):
    try:
        if url.startswith("Error"):
            return []
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=12, headers=headers)
        if response.status_code == 200:
            return extract_emails_from_html(response.text)
    except Exception:
        pass
    return []

# Main logic
if st.button("🔍 Start Email Search") and df is not None:
    with st.spinner("Processing... Please wait..."):
        service = build("customsearch", "v1", developerKey=API_KEY)
        results = []

        for idx, row in df.iterrows():
            name = str(row["Name"])
            reg_no = row["Registration No."]
            address = row["Address"]

            website = get_best_website_for_name(name, service)
            emails = crawl_and_get_emails(website) if website else []

            results.append({
                "Name": name,
                "Registration No.": reg_no,
                "Address": address,
                "Website": website if website else "Not found",
                "Emails": ", ".join(emails) if emails else "Not found"
            })

            # Optional: Respect rate limits
            time.sleep(1.2)

        output_df = pd.DataFrame(results)
        found_count = output_df[output_df["Emails"] != "Not found"].shape[0]

        st.success(f"🎉 Found email addresses for {found_count} of {len(output_df)} investors.")
        st.dataframe(output_df)

        st.download_button(
            label="📥 Download Results",
            data=output_df.to_csv(index=False).encode("utf-8"),
            file_name="fpi_emails_output.csv",
            mime="text/csv"
        )

        # Optional word cloud
        all_emails = [email for row in results for email in row["Emails"].split(", ") if "@" in email]
        if all_emails:
            domains = [e.split("@")[1] for e in all_emails]
            domain_text = " ".join(domains)
            st.subheader("📊 Word Cloud of Email Domains")
            wordcloud = WordCloud(width=800, height=300, background_color='white').generate(domain_text)
            plt.figure(figsize=(8, 3))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            st.pyplot(plt)

# Self-hosting
st.markdown("""
---
### 🛠 Self-Hosting
You can host this app yourself.  
👉 [Download Source Code](https://dhruvbansal8.gumroad.com/l/hhwbm)
""")
