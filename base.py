import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
import pandas as pd
import platform

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

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("Website Performance Analyzer")
st.markdown("Enter a website URL and select a browser to measure loading speed and analyze performance.")

url = st.text_input("Enter the URL to evaluate (e.g., https://www.google.com):", "https://streamlit.io")

# Dynamically build browser list (exclude Safari if not on macOS)
browser_options = ["All Browsers", "Chrome", "Firefox", "Edge"]
if platform.system() == "Darwin":
    browser_options.append("Safari")

browser_choice = st.selectbox(
    "Choose a browser for analysis:",
    browser_options
)

if st.button("Analyze Website Performance"):
    if url:
        if browser_choice == "All Browsers":
            browsers_to_test = ["Chrome", "Firefox", "Edge"]
            if platform.system() == "Darwin":
                browsers_to_test.append("Safari")
        else:
            browsers_to_test = [browser_choice]

        comparison_results = []

        for browser in browsers_to_test:
            st.markdown("---")
            st.header(f"Analysis for: {browser}")

            with st.spinner(f"Testing on {browser}... This may take a moment."):
                result = get_website_speed(url, browser)

            if "Error" in result:
                st.error(f"Could not complete analysis on {browser}: {result['Error']}")
                continue

            comparison_results.append({
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
                    st.markdown("This chart shows the total time spent loading each type of resource.")

                    st.subheader("Top 20 Slowest Resources")
                    slowest_resources = df.sort_values(by="Duration (ms)", ascending=False).head(20)
                    st.dataframe(slowest_resources[["Name", "Type", "Duration (ms)"]], width="stretch")
                    st.markdown("This table highlights the individual assets that took the longest to load.")
                else:
                    st.warning("No detailed resource data was collected for this page.")
            else:
                st.warning("No detailed resource data was collected for this page.")

        # --- Comparison Section ---
        if len(comparison_results) > 1:
            st.markdown("---")
            st.header("Browser Comparison Summary")

            comp_df = pd.DataFrame(comparison_results)

            # Add qualitative assessment
            def assess_speed(value):
                if value < 1000:
                    return "Excellent"
                elif value <= 3000:
                    return "Acceptable"
                else:
                    return "Slow"

            comp_df["Assessment"] = comp_df["Total (ms)"].apply(assess_speed)

            st.subheader("Total Page Load Time Comparison")
            st.bar_chart(comp_df.set_index("Browser")["Total (ms)"])

            st.subheader("Detailed Performance Metrics")
            st.dataframe(comp_df.set_index("Browser"), width="stretch")

            # CSV Download Button
            csv = comp_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Comparison as CSV",
                data=csv,
                file_name="browser_comparison.csv",
                mime="text/csv"
            )

    else:
        st.warning("Please enter a valid URL to begin the analysis.")
