import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
import pandas as pd
import platform
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# --- Website Speed Analyzer ---
def get_website_speed(url, browser_name):
    driver = None
    try:
        # --- Browser Setup ---
        if browser_name == "Chrome":
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(options=options)
        elif browser_name == "Firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")
            driver = webdriver.Firefox(options=options)
        elif browser_name == "Edge":
            options = EdgeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Edge(options=options)
        elif browser_name == "Safari":
            if platform.system() != "Darwin":
                return {"Error": "Safari testing is only supported on macOS with SafariDriver enabled."}
            driver = webdriver.Safari()
        else:
            return {"Error": "Unsupported browser selected."}

        driver.get(url)

        # --- Modern Navigation Timing API ---
        nav_timing = driver.execute_script("return performance.getEntriesByType('navigation')[0];")

        if not nav_timing:
            return {"Error": "Navigation timing data is unavailable."}

        backend_performance = nav_timing.get('responseStart', 0) - nav_timing.get('startTime', 0)
        frontend_performance = nav_timing.get('domComplete', 0) - nav_timing.get('responseStart', 0)
        total_load_time = nav_timing.get('duration', 0)

        # --- Resource Timings ---
        resource_timings = driver.execute_script("return window.performance.getEntriesByType('resource');")

        resource_data = []
        for resource in resource_timings:
            name = resource.get('name', '')
            display_name = name.split('/')[-1] if "/" in name else name
            resource_data.append({
                "Name": display_name or name,
                "URL": name,
                "Type": resource.get('initiatorType', 'unknown'),
                "Duration (ms)": resource.get('duration', 0)
            })

        return {
            "Backend Performance (ms)": backend_performance,
            "Frontend Performance (ms)": frontend_performance,
            "Total Page Load Time (ms)": total_load_time,
            "Resource Data": resource_data
        }
    except Exception as e:
        return {"Error": f"An unexpected error occurred: {str(e)}"}
    finally:
        if driver:
            driver.quit()

# --- Collect internal links (limit 10) ---
def collect_internal_links(base_url, max_links=10):
    try:
        resp = requests.get(base_url, timeout=5)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        parsed_base = urlparse(base_url)
        domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = urljoin(domain, a_tag['href'])
            parsed_href = urlparse(href)
            if parsed_href.netloc == parsed_base.netloc:
                links.add(href)
            if len(links) >= max_links:
                break

        return list(links)
    except Exception:
        return []

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("Website Performance Analyzer")
st.markdown("Analyze loading speed and resources for a page or multiple internal pages.")

url = st.text_input("Enter the base URL to evaluate (e.g., https://www.example.com):", "https://streamlit.io")

# Scope selection
test_scope = st.radio("Choose scope of analysis:", ["Test only this page", "Test up to 10 internal pages"])

# Dynamically build browser list
browser_options = ["All Browsers", "Chrome", "Firefox", "Edge"]
if platform.system() == "Darwin":
    browser_options.append("Safari")
browser_choice = st.selectbox("Choose a browser for analysis:", browser_options)

if st.button("Analyze Website Performance"):
    if url:
        # Determine pages to test
        if test_scope == "Test only this page":
            pages_to_test = [url]
        else:
            pages_to_test = [url] + collect_internal_links(url, max_links=10)
            st.markdown(f"Found {len(pages_to_test)} pages to test.")

        if browser_choice == "All Browsers":
            browsers_to_test = ["Chrome", "Firefox", "Edge"]
            if platform.system() == "Darwin":
                browsers_to_test.append("Safari")
        else:
            browsers_to_test = [browser_choice]

        all_results = []

        for page in pages_to_test:
            st.markdown("---")
            st.header(f"Page: {page}")
            page_results = []

            for browser in browsers_to_test:
                with st.spinner(f"Testing {browser}... This may take a moment."):
                    result = get_website_speed(page, browser)

                if "Error" in result:
                    st.error(f"Could not complete analysis on {browser}: {result['Error']}")
                    continue

                page_results.append({
                    "Page": page,
                    "Browser": browser,
                    "Backend (ms)": result.get('Backend Performance (ms)', 0),
                    "Frontend (ms)": result.get('Frontend Performance (ms)', 0),
                    "Total (ms)": result.get('Total Page Load Time (ms)', 0)
                })

                col1, col2, col3 = st.columns(3)
                col1.metric("Backend Performance", f"{result.get('Backend Performance (ms)', 0)} ms")
                col2.metric("Frontend Performance", f"{result.get('Frontend Performance (ms)', 0)} ms")
                col3.metric("Total Load Time", f"{result.get('Total Page Load Time (ms)', 0)} ms")

                if result.get("Resource Data"):
                    df = pd.DataFrame(result["Resource Data"])
                    if not df.empty:
                        st.subheader("Resource Load Time by Type")
                        type_summary = df.groupby("Type")["Duration (ms)"].sum().sort_values(ascending=False)
                        st.bar_chart(type_summary)

                        st.subheader("Top 20 Slowest Resources")
                        slowest_resources = df.sort_values(by="Duration (ms)", ascending=False).head(20)
                        st.dataframe(slowest_resources[["Name", "Type", "Duration (ms)"]], width="stretch")
            
            all_results.extend(page_results)

        # --- Overall Summary ---
        if all_results:
            comp_df = pd.DataFrame(all_results)
            comp_df['Assessment'] = comp_df['Total (ms)'].apply(lambda x: 'Excellent' if x<1000 else ('Acceptable' if x<=3000 else 'Slow'))

            st.markdown("---")
            st.header("Overall Summary")

            st.subheader("Average Metrics per Browser")
            avg_df = comp_df.groupby('Browser')[['Backend (ms)','Frontend (ms)','Total (ms)']].mean().round(2).reset_index()
            st.dataframe(avg_df, width="stretch")

            st.subheader("Full Per-Page Results")
            st.dataframe(comp_df, width="stretch")

            # CSV Download
            csv = comp_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="Download all results as CSV", data=csv, file_name="website_performance.csv", mime="text/csv")

    else:
        st.warning("Please enter a valid URL to begin the analysis.")
