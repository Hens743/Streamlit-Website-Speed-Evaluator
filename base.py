import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from urllib.parse import urlparse

# --- Helper Functions ---

def is_valid_url(url):
    """Checks if the provided string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_metric_rating(metric, value):
    """Returns a rating and color for a given performance metric value."""
    if metric == "TTFB":
        if value < 800: return "Good ✅"
        if value < 1800: return "Needs Improvement ⚠️"
        return "Poor ❌"
    elif metric == "LoadTime":
        if value < 2500: return "Good ✅"
        if value < 4000: return "Needs Improvement ⚠️"
        return "Poor ❌"
    return ""

# --- Core Selenium Logic with Caching ---

# @st.cache_data tells Streamlit to cache the output of this function.
# Selenium tests are slow, so this prevents re-running them for the same URL.
@st.cache_data
def get_website_speed(url, browser_name):
    """
    Measures the page load time and resource loading performance of a website.
    """
    driver = None
    try:
        # --- Driver Setup ---
        headless_options = ["--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--window-size=1920,1080"]
        if browser_name == "Chrome":
            options = ChromeOptions()
            for arg in headless_options: options.add_argument(arg)
            driver = webdriver.Chrome(options=options)
        elif browser_name == "Firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")
            driver = webdriver.Firefox(options=options)
        elif browser_name == "Edge":
            options = EdgeOptions()
            for arg in headless_options: options.add_argument(arg)
            driver = webdriver.Edge(options=options)
        else:
            raise ValueError("Unsupported browser selected.")

        # --- Performance Measurement ---
        driver.get(url)
        timing_info = driver.execute_script("return window.performance.timing;")
        
        # --- Key Timestamps ---
        navigation_start = timing_info.get('navigationStart', 0)
        response_start = timing_info.get('responseStart', 0)
        dom_complete = timing_info.get('domComplete', 0)
        domain_lookup_start = timing_info.get('domainLookupStart', 0)
        domain_lookup_end = timing_info.get('domainLookupEnd', 0)
        connect_start = timing_info.get('connectStart', 0)
        connect_end = timing_info.get('connectEnd', 0)

        if dom_complete == 0 or navigation_start == 0:
            return {"Error": "Page did not finish loading or timing data is unavailable."}

        # --- Calculate Metrics ---
        result = {
            "Time to First Byte (ms)": response_start - navigation_start,
            "Frontend Performance (ms)": dom_complete - response_start,
            "Total Page Load Time (ms)": dom_complete - navigation_start,
            "DNS Lookup Time (ms)": domain_lookup_end - domain_lookup_start,
            "TCP Connection Time (ms)": connect_end - connect_start
        }

        # --- Resource Timings ---
        resource_timings = driver.execute_script("return window.performance.getEntriesByType('resource');")
        result["Resource Data"] = [{
            "Name": resource.get('name', '').split('/')[-1].split('?')[0],
            "URL": resource.get('name', ''),
            "Type": resource.get('initiatorType', 'unknown'),
            "Duration (ms)": resource.get('duration', 0)
        } for resource in resource_timings]

        return result
    except Exception as e:
        return {"Error": f"An unexpected error occurred: {str(e)}"}
    finally:
        if driver:
            driver.quit()

# --- Streamlit App UI ---
st.set_page_config(layout="wide", page_title="Web Performance Analyzer")
st.title("Website Performance Analyzer 🚀")
st.markdown("Enter a URL and select browsers to measure loading speed and analyze resource performance.")

# --- UI Controls ---
url = st.text_input("Enter the URL to evaluate:", "https://streamlit.io")
available_browsers = ["Chrome", "Firefox", "Edge"]
selected_browsers = st.multiselect(
    "Select browsers to test:",
    options=available_browsers,
    default=available_browsers  # Edge is now a default
)

if st.button("Analyze Website Performance"):
    if not is_valid_url(url):
        st.error("Please enter a valid URL (e.g., https://www.google.com).")
    elif not selected_browsers:
        st.warning("Please select at least one browser to test.")
    else:
        all_results_for_comparison = []
        for browser in selected_browsers:
            st.markdown("---")
            st.header(f"Analysis for: {browser}")

            with st.spinner(f"Testing on {browser}... This may take a moment (first run is slow, subsequent runs are cached)."):
                result = get_website_speed(url, browser)

            if "Error" in result:
                st.error(f"Could not complete analysis on {browser}: {result['Error']}")
                continue

            # Store results for the final comparison plot
            all_results_for_comparison.append({
                "Browser": browser,
                "Total Page Load Time (ms)": result.get("Total Page Load Time (ms)", 0),
                "Time to First Byte (ms)": result.get("Time to First Byte (ms)", 0),
                "Frontend Performance (ms)": result.get("Frontend Performance (ms)", 0),
            })

            # --- Display Metrics ---
            ttfb = result.get('Time to First Byte (ms)', 0)
            total_load = result.get('Total Page Load Time (ms)', 0)

            st.subheader("Core Web Vitals")
            cols = st.columns(3)
            with cols[0]:
                st.metric("Time to First Byte (TTFB)", f"{ttfb} ms", delta=get_metric_rating('TTFB', ttfb), delta_color="off")
            with cols[1]:
                 st.metric("Total Load Time", f"{total_load} ms", delta=get_metric_rating('LoadTime', total_load), delta_color="off")
            
            st.subheader("Connection Details")
            cols = st.columns(3)
            with cols[0]:
                st.metric("DNS Lookup", f"{result.get('DNS Lookup Time (ms)', 0)} ms")
            with cols[1]:
                st.metric("TCP Connection", f"{result.get('TCP Connection Time (ms)', 0)} ms")
            with cols[2]:
                st.metric("Frontend Processing", f"{result.get('Frontend Performance (ms)', 0)} ms")

            # --- Display Resource Analysis in Expanders ---
            if result.get("Resource Data"):
                df = pd.DataFrame(result["Resource Data"])
                if not df.empty:
                    with st.expander("📊 View Resource Load Time by Type"):
                        type_summary = df.groupby("Type")["Duration (ms)"].sum().sort_values(ascending=False)
                        st.bar_chart(type_summary)

                    with st.expander("📜 View Top 30 Slowest Resources"):
                        slowest_resources = df.sort_values(by="Duration (ms)", ascending=False).head(30)
                        st.dataframe(slowest_resources[["Name", "Type", "Duration (ms)"]].style.format({"Duration (ms)": "{:.2f}"}))

        # --- Browser Comparison Section ---
        if len(all_results_for_comparison) > 1:
            st.markdown("---")
            st.header("📊 Browser Performance Comparison")
            comparison_df = pd.DataFrame(all_results_for_comparison).set_index("Browser")
            st.markdown("This chart compares key metrics across browsers. Lower is better.")
            st.bar_chart(comparison_df)
