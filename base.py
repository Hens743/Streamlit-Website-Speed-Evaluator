import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from urllib.parse import urlparse

# --- Helper function to validate URL ---
def is_valid_url(url):
    """Checks if the provided string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

# --- Refactored function to set up the WebDriver ---
def setup_driver(browser_name):
    """Initializes and returns a Selenium WebDriver for the specified browser."""
    if browser_name == "Chrome":
        options = ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
    elif browser_name == "Firefox":
        options = FirefoxOptions()
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options)
    # Edge is commented out but can be enabled if needed
    # elif browser_name == "Edge":
    #     options = EdgeOptions()
    #     options.add_argument("--headless")
    #     options.add_argument("--no-sandbox")
    #     options.add_argument("--disable-dev-shm-usage")
    #     options.add_argument("--disable-gpu")
    #     driver = webdriver.Edge(options=options)
    else:
        raise ValueError("Unsupported browser selected.")
    return driver

# --- Core analysis function ---
def get_website_speed(url, browser_name):
    """
    Measures the page load time and resource loading performance of a website.
    """
    driver = None
    try:
        driver = setup_driver(browser_name)
        driver.get(url)

        timing_info = driver.execute_script("return window.performance.timing;")
        navigation_start = timing_info.get('navigationStart', 0)
        response_start = timing_info.get('responseStart', 0)
        dom_complete = timing_info.get('domComplete', 0)

        if dom_complete == 0 or navigation_start == 0:
            return {"Error": "Page did not finish loading or timing data is unavailable."}

        ttfb = response_start - navigation_start
        frontend_performance = dom_complete - response_start
        total_load_time = dom_complete - navigation_start

        resource_timings = driver.execute_script("return window.performance.getEntriesByType('resource');")
        resource_data = [{
            "Name": resource.get('name', '').split('/')[-1].split('?')[0],
            "URL": resource.get('name', ''),
            "Type": resource.get('initiatorType', 'unknown'),
            "Duration (ms)": resource.get('duration', 0)
        } for resource in resource_timings]

        return {
            "Time to First Byte (ms)": ttfb,
            "Frontend Performance (ms)": frontend_performance,
            "Total Page Load Time (ms)": total_load_time,
            "Resource Data": resource_data
        }
    except Exception as e:
        return {"Error": f"An unexpected error occurred: {str(e)}"}
    finally:
        if driver:
            driver.quit()

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("Website Performance Analyzer 🌐")
st.markdown("Enter a URL and select browsers to measure loading speed and analyze resource performance.")

# --- UI Controls ---
url = st.text_input("Enter the URL to evaluate:", "https://streamlit.io")
available_browsers = ["Chrome", "Firefox"]
selected_browsers = st.multiselect(
    "Select browsers to test:",
    options=available_browsers,
    default=available_browsers
)

if st.button("Analyze Website Performance"):
    if not is_valid_url(url):
        st.error("Please enter a valid URL (e.g., https://www.google.com).")
    elif not selected_browsers:
        st.warning("Please select at least one browser to test.")
    else:
        # **NEW: List to hold results for final comparison**
        all_results_for_comparison = []

        for browser in selected_browsers:
            st.markdown("---")
            st.header(f"Analysis for: {browser}")

            with st.spinner(f"Testing on {browser}... This may take a moment."):
                result = get_website_speed(url, browser)

            if "Error" in result:
                st.error(f"Could not complete analysis on {browser}: {result['Error']}")
                continue

            # **NEW: Store the main metrics for the summary plot**
            all_results_for_comparison.append({
                "Browser": browser,
                "Total Page Load Time (ms)": result.get("Total Page Load Time (ms)", 0),
                "Time to First Byte (ms)": result.get("Time to First Byte (ms)", 0),
                "Frontend Performance (ms)": result.get("Frontend Performance (ms)", 0),
            })

            # Display individual metrics for the current browser
            col1, col2, col3 = st.columns(3)
            col1.metric("Time to First Byte (TTFB)", f"{result.get('Time to First Byte (ms)', 0)} ms")
            col2.metric("Frontend Processing", f"{result.get('Frontend Performance (ms)', 0)} ms")
            col3.metric("Total Load Time", f"{result.get('Total Page Load Time (ms)', 0)} ms")

            # Display resource analysis for the current browser
            if result.get("Resource Data"):
                df = pd.DataFrame(result["Resource Data"])
                if not df.empty:
                    st.subheader("Resource Load Time by Type")
                    type_summary = df.groupby("Type")["Duration (ms)"].sum().sort_values(ascending=False)
                    st.bar_chart(type_summary)

                    st.subheader("Top 5 Slowest Resources")
                    slowest_resources = df.sort_values(by="Duration (ms)", ascending=False).head(5)
                    st.dataframe(slowest_resources[["Name", "Type", "Duration (ms)"]].style.format({"Duration (ms)": "{:.2f}"}))

        # --- **NEW: Browser Comparison Section** ---
        if len(all_results_for_comparison) > 1:
            st.markdown("---")
            st.header("📊 Browser Performance Comparison")
            
            # Convert the collected results into a DataFrame
            comparison_df = pd.DataFrame(all_results_for_comparison)
            comparison_df = comparison_df.set_index("Browser")
            
            st.markdown("This chart compares the key performance metrics across the selected browsers. Lower is better.")
            st.bar_chart(comparison_df)
