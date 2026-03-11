"""
view_template.py — Starter template for a new dashboard page.

Steps
-----
1. Copy to ``dashboard/pages/NN_YourPage.py``
2. Replace every TODO value
3. Delete this docstring and any sections you don't need
4. Run: streamlit run dashboard/app.py

Design system notes
-------------------
- Base colours, fonts, and dark theme are set in .streamlit/config.toml.
  You do not need to set any colours manually in page code.
- ``apply_theme()`` adds borders, label styles, and responsive breakpoints
  on top of config.toml.  Call it once, right after set_page_config.
- ``kpi_row()`` uses native st.metric + st.columns.  It inherits the theme
  automatically and wraps to a single column on mobile via the CSS in
  apply_theme().
- Never use hardcoded pixel margins for layout — use st.columns / st.container
  and let the grid handle spacing.
"""
from __future__ import annotations

import streamlit as st

# ui_components and utils are importable because Streamlit adds dashboard/ to sys.path.
from ui_components import (
    apply_theme,
    empty_state,
    kpi_row,
    page_header,
    section_divider,
)
from utils import load_jobs  # TODO: swap / add loaders as needed

# ── 1. Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TODO: Page Title",
    page_icon="📄",          # TODO: pick an emoji
    layout="wide",
)

# ── 2. Theme ───────────────────────────────────────────────────────────────────
apply_theme()

# ── 3. Load data ───────────────────────────────────────────────────────────────
jobs_df = load_jobs()

if jobs_df.empty:
    page_header("TODO: Page Title")
    empty_state("No job data available yet.")
    st.stop()

# ── 4. Sidebar filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## TODO: Sidebar Title")
    section_divider()

    # Example filter — uncomment and adjust as needed:
    # provinces = ["All Provinces"] + sorted(jobs_df["location_state"].dropna().unique())
    # province_filter = st.selectbox("Province", provinces)

# ── 5. Apply filters ───────────────────────────────────────────────────────────
filtered = jobs_df.copy()
# TODO: apply your sidebar filter values here, e.g.:
# if province_filter != "All Provinces":
#     filtered = filtered[filtered["location_state"] == province_filter]

# ── 6. Page header ─────────────────────────────────────────────────────────────
# page_header() calls st.title() (theme-aware) + an optional muted subtitle line.
page_header(
    title="TODO: Page Title",
    subtitle=f"TODO: subtitle · {len(filtered):,} jobs analysed",
)

# ── 7. KPI row ─────────────────────────────────────────────────────────────────
# kpi_row() uses st.columns internally.
# The apply_theme() media query wraps columns below 640 px (mobile).
kpi_row([
    ("TODO Metric 1", "—"),
    ("TODO Metric 2", "—"),
    ("TODO Metric 3", "—"),
    ("TODO Metric 4", "—"),
])

section_divider()

# ── 8. Two-column layout ───────────────────────────────────────────────────────
# st.columns proportions: [3, 2] gives a wider left panel.
# On narrow viewports the apply_theme() media query wraps them to full width.
with st.container():
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.subheader("TODO: Primary chart")
        if filtered.empty:
            empty_state()
        else:
            # st.plotly_chart(fig, use_container_width=True)
            st.info("Replace with your main chart.")

    with col_right:
        st.subheader("TODO: Secondary content")
        # Could be a smaller chart, a filtered table, or a text summary.
        st.info("Replace with secondary content.")

# ── 9. Full-width section ──────────────────────────────────────────────────────
section_divider("Detail")

with st.container():
    st.subheader("TODO: Full-width section")
    # st.dataframe(filtered[["col_a", "col_b"]], use_container_width=True)
    st.info("Replace with a full-width chart or table.")
