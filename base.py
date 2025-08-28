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

def get_resource_rating_and_tip(row):
    """Analyzes a resource (DataFrame row) and returns a rating and optimization tip."""
    res_type, duration, size = row["Type"], row["Duration (ms)"], row["Size (KB)"]
    rating, tip = "Good ✅", "No action needed."

    if res_type in ["script", "css"]:
        if duration > 500 or size > 150:
            rating, tip = "Poor ❌", "Critical resource. Defer if possible, minify, and reduce size."
        elif duration > 200 or size > 75:
            rating, tip = "Needs Improvement ⚠️", "This resource is blocking rendering. Try to minify and optimize delivery."
    elif res_type == "img":
        if size > 500:
            rating, tip = "Poor ❌", "Very large image. Compress heavily and use a modern format like WebP/AVIF."
        elif size > 200:
            rating, tip = "Needs Improvement ⚠️", "Large image. Compress and consider resizing to the displayed dimensions."
    elif res_type == "font" and (duration > 700 or size > 150):
        rating, tip = "Poor ❌", "Large font file. Use WOFF2 format and preload critical fonts."

    if rating == "Good ✅" and duration > 1000:
        rating, tip = "Needs Improvement ⚠️", "This resource took a long time to load. Investigate network latency."
    
    return rating, tip

# --- Core Selenium Logic with Caching ---

@st.cache_data
def get_website_speed(url, browser_name):
    """Measures the page load time and resource loading performance of a website."""
    driver = None
    try:
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

        driver.get(url)
        timing_info = driver.execute_script("return window.performance.timing;")
        
        navigation_start = timing_info.get('navigationStart', 0)
        response_start = timing_info.get('responseStart', 0)
        dom_complete = timing_info.get('domComplete', 0)
        domain_lookup_start = timing_info.get('domainLookupStart', 0)
        domain_lookup_end = timing_info.get('domainLookupEnd', 0)
        connect_start = timing_info.get('connectStart', 0)
        connect_end = timing_info.get('connectEnd', 0)

        if dom_complete == 0: return {"Error": "Page did not finish loading."}

        result = {
            "Time to First Byte (ms)": response_start - navigation_start,
            "Frontend Performance (ms)": dom_complete - response_start,
            "Total Page Load Time (ms)": dom_complete - navigation_start,
            "DNS Lookup Time (ms)": domain_lookup_end - domain_lookup_start,
            "TCP Connection Time (ms)": connect_end - connect_start
        }

        resource_timings = driver.execute_script("""
            return window.performance.getEntriesByType('resource').map(entry => ({
                name: entry.name, initiatorType: entry.initiatorType,
                duration: entry.duration, transferSize: entry.transferSize }));
        """)
        
        result["Resource Data"] = [{
            "Name": resource.get('name', '').split('/')[-1].split('?')[0],
            "Type": resource.get('initiatorType', 'unknown'),
            "Duration (ms)": resource.get('duration', 0),
            "Size (KB)": resource.get('transferSize', 0) / 1024
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
st.markdown("Enter a URL to measure its performance and get actionable optimization tips.")

url = st.text_input("Enter the URL to evaluate:", "https://streamlit.io")
available_browsers = ["Chrome", "Firefox", "Edge"]
selected_browsers = st.multiselect("Select browsers:", options=available_browsers, default=available_browsers)

if st.button("Analyze Website Performance"):
    if not is_valid_url(url):
        st.error("Please enter a valid URL.")
    elif not selected_browsers:
        st.warning("Please select at least one browser.")
    else:
        # RE-ADDED: List to hold results for final comparison
        all_results_for_comparison = []

        for browser in selected_browsers:
            st.markdown("---")
            st.header(f"Analysis for: {browser}")
            result = get_website_speed(url, browser)
            if "Error" in result:
                st.error(f"Could not complete analysis: {result['Error']}")
                continue

            # RE-ADDED: Store results for the final comparison plot
            all_results_for_comparison.append({
                "Browser": browser,
                "Total Page Load Time (ms)": result.get("Total Page Load Time (ms)", 0),
                "Time to First Byte (ms)": result.get("Time to First Byte (ms)", 0),
                "Frontend Performance (ms)": result.get("Frontend Performance (ms)", 0),
            })
            
            # --- Display Metrics with Popover Benchmarks ---
            st.subheader("Core Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Time to First Byte (TTFB)", f"{result.get('Time to First Byte (ms)', 0)} ms")
                with st.popover("ℹ️", use_container_width=True): st.markdown("**Excellent:** < 500 ms, **Good:** 501-800 ms, **Needs Improvement:** 801-1800 ms, **Poor:** > 1800 ms")
            with col2:
                st.metric("Total Page Load Time", f"{result.get('Total Page Load Time (ms)', 0)} ms")
                with st.popover("ℹ️", use_container_width=True): st.markdown("**Excellent:** < 2000 ms, **Good:** 2001-2500 ms, **Needs Improvement:** 2501-4000 ms, **Poor:** > 4000 ms")

            # RE-ADDED: Detailed connection and frontend metrics
            st.subheader("Performance Breakdown")
            col1, col2, col3 = st.columns(3)
            col1.metric("DNS Lookup", f"{result.get('DNS Lookup Time (ms)', 0)} ms")
            col2.metric("TCP Connection", f"{result.get('TCP Connection Time (ms)', 0)} ms")
            col3.metric("Frontend Processing", f"{result.get('Frontend Performance (ms)', 0)} ms")
            
            # --- Display Resource Analysis with NEW Smart Table ---
            st.subheader("Resource Analysis")
            if result.get("Resource Data"):
                df = pd.DataFrame(result["Resource Data"])
                if not df.empty:
                    # RE-ADDED: Bar chart for resource types
                    with st.expander("📊 View Resource Load Time by Type"):
                        type_summary = df.groupby("Type")["Duration (ms)"].sum().sort_values(ascending=False)
                        st.bar_chart(type_summary)

                    with st.expander("📜 View Top 30 Slowest Resources with Optimization Tips", expanded=True):
                        slowest_resources = df.sort_values(by="Duration (ms)", ascending=False).head(30)
                        ratings_tips = slowest_resources.apply(get_resource_rating_and_tip, axis=1, result_type='expand')
                        slowest_resources[['Rating', 'Optimization Tip']] = ratings_tips
                        st.dataframe(slowest_resources[["Name", "Type", "Duration (ms)", "Size (KB)", "Rating", "Optimization Tip"]],
                                     use_container_width=True, hide_index=True,
                                     column_config={
                                         "Duration (ms)": st.column_config.NumberColumn(format="%d ms"),
                                         "Size (KB)": st.column_config.NumberColumn(format="%.1f KB")
                                     })

        # RE-ADDED: Final Browser Comparison Chart Section
        if len(all_results_for_comparison) > 1:
            st.markdown("---")
            st.header("📊 Final Browser Performance Comparison")
            comparison_df = pd.DataFrame(all_results_for_comparison).set_index("Browser")
            st.markdown("This chart compares key metrics across browsers. Lower is better.")
            st.bar_chart(comparison_df)
