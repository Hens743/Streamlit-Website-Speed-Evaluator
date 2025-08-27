import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
import pandas as pd
import os

def get_website_speed(url, browser_name):
    """
    Measures the page load time and resource loading performance of a website using Selenium.
    """
    driver = None
    try:
        # --- Headless Browser Setup ---
        # This configures the browser to run in the background without a visible UI.
        if browser_name == "Chrome":
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            # Let Selenium's new manager handle the driver automatically
            driver = webdriver.Chrome(options=options)
        elif browser_name == "Firefox":
            # Firefox setup remains the same as it's often less problematic
            options = FirefoxOptions()
            options.add_argument("--headless")
            driver = webdriver.Firefox(options=options)
        elif browser_name == "Edge":
            # Note: Edge support on Streamlit Cloud can be less stable.
            # This setup is experimental.
            options = EdgeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Edge(options=options)
        else:
            return {"Error": "Unsupported browser selected."}

        driver.get(url)

        # --- Use Navigation Timing API for Core Metrics ---
        timing_info = driver.execute_script("return window.performance.timing;")
        navigation_start = timing_info.get('navigationStart', 0)
        response_start = timing_info.get('responseStart', 0)
        dom_complete = timing_info.get('domComplete', 0)

        if dom_complete == 0 or navigation_start == 0:
             return {"Error": "Page did not finish loading or timing data is unavailable."}

        backend_performance = response_start - navigation_start
        frontend_performance = dom_complete - response_start
        total_load_time = dom_complete - navigation_start

        # --- Get Detailed Resource Timings ---
        resource_timings = driver.execute_script("return window.performance.getEntriesByType('resource');")

        resource_data = []
        for resource in resource_timings:
            resource_data.append({
                "Name": resource.get('name', '').split('/')[-1],
                "URL": resource.get('name', ''),
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

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("Website Performance Analyzer")
st.markdown("Enter a website URL to measure its loading speed and analyze its resource performance across different browsers.")

url = st.text_input("Enter the URL to evaluate (e.g., https://www.google.com):", "https://streamlit.io")

if st.button("Analyze Website Performance"):
    if url:
        # Re-enabling all browsers for testing
        browsers_to_test = ["Chrome", "Firefox", "Edge"] 
        
        for browser in browsers_to_test:
            st.markdown(f"---")
            st.header(f"Analysis for: {browser}")

            with st.spinner(f"Testing on {browser}... This may take a moment."):
                result = get_website_speed(url, browser)

            if "Error" in result:
                st.error(f"Could not complete analysis on {browser}: {result['Error']}")
                continue

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
                    st.markdown("This chart shows the total time spent loading each type of resource.")

                    st.subheader("Top 5 Slowest Resources")
                    slowest_resources = df.sort_values(by="Duration (ms)", ascending=False).head(5)
                    st.dataframe(slowest_resources[["Name", "Type", "Duration (ms)"]], width='stretch')
                    st.markdown("This table highlights the individual assets that took the longest to load.")
                else:
                    st.warning("No detailed resource data was collected for this page.")
            else:
                st.warning("No detailed resource data was collected for this page.")
    else:
        st.warning("Please enter a valid URL to begin the analysis.")
