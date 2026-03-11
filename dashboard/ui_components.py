"""
ui_components.py — Shared design system for the DataScienceJobs dashboard.

Base colours and typography are set in .streamlit/config.toml.
This module provides the fine-grained CSS overrides that config.toml cannot
express (borders, label styles, responsive grid breakpoints) plus reusable
Python helpers so pages never write raw HTML.

Usage
-----
from ui_components import apply_theme, kpi_row, page_header, section_divider

Call ``apply_theme()`` right after ``st.set_page_config()``.
"""
from __future__ import annotations

import html as _html

import streamlit as st

# ── Colour palette ─────────────────────────────────────────────────────────────
# These mirror .streamlit/config.toml — update both together.

BG          = "#0d1b2a"   # backgroundColor  (config.toml)
SURFACE     = "#102035"   # secondaryBackgroundColor (config.toml)
SURFACE_ALT = "#152d45"   # slightly lighter surface (inputs on hover, etc.)
BORDER      = "#1e3a5f"   # all borders / hr / dividers
SIDEBAR_BG  = SURFACE     # sidebar uses secondaryBackgroundColor

TEXT        = "#e2eaf4"   # textColor (config.toml)
SUBTEXT     = "#7fa8c9"   # secondary labels
MUTED       = "#a8c0d6"   # sidebar body text, captions

# Accent colours — referenced in page charts and badges.
ACCENT_BLUE   = "#3b82f6"   # primaryColor (config.toml); Languages
ACCENT_PINK   = "#f472b6"   # Modeling / Senior+
ACCENT_GREEN  = "#10b981"   # Analytics / Salary
ACCENT_AMBER  = "#f59e0b"   # Infrastructure / Remote
ACCENT_SLATE  = "#64748b"   # neutral / Other
ACCENT_VIOLET = "#8b5cf6"   # spare

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"


# ── CSS overrides (config.toml handles background, text colour, font) ─────────
# Only rules that config.toml cannot express live here: borders, label styling,
# component-level tweaks, and responsive breakpoints.

_OVERRIDE_CSS = f"""
<style>
/* ── Sidebar border + muted text ── */
[data-testid="stSidebar"] {{
    border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stRadio > label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {{
    color: {MUTED} !important;
    font-size: 0.85rem;
}}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    color: {TEXT} !important;
}}

/* ── Metric containers — border + label styling ── */
[data-testid="metric-container"] {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 12px 16px;
}}
[data-testid="metric-container"] label {{
    color: {SUBTEXT} !important;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}

/* ── Dividers ── */
hr {{ border-color: {BORDER}; }}

/* ── Select border ── */
div[data-baseweb="select"] > div {{
    border-color: {BORDER} !important;
}}

/* ── Radio buttons ── */
div[data-testid="stRadio"] > div {{
    flex-wrap: wrap;
    gap: 4px 16px;
    row-gap: 6px;
}}
div[data-testid="stRadio"] label {{
    font-size: 0.875rem !important;
    cursor: pointer;
}}
div[data-testid="stRadio"] label:has(input:checked) {{
    font-weight: 600 !important;
}}
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    font-size: 0.8rem;
    color: {SUBTEXT};
}}

/* ── DataFrames ── */
.stDataFrame {{
    border-radius: 8px;
    border: 1px solid {BORDER};
}}

/* ── Plotly charts ── */
[data-testid="stPlotlyChart"] {{
    border-radius: 12px;
    overflow: hidden;
}}

/* ── KPI card grid ─────────────────────────────────────────────────────────
   Used by kpi_row_html(). Responsive breakpoints here mean the caller never
   needs to specify columns — the grid adapts automatically.
   ── */
.dsj-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(var(--kpi-cols, 4), 1fr);
    gap: 12px;
    margin-bottom: 16px;
}}
@media (max-width: 768px) {{
    .dsj-kpi-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
}}
@media (max-width: 480px) {{
    .dsj-kpi-grid {{ grid-template-columns: 1fr !important; }}
}}

/* ── Streamlit columns: wrap on narrow viewports ───────────────────────────
   Targets only the main content area (not sidebar) so sidebar layout is
   unaffected. Columns flex-wrap below 640 px (phone landscape / portrait).
   ── */
@media (max-width: 640px) {{
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] {{
        flex-wrap: wrap;
    }}
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]
    > [data-testid="stColumn"] {{
        min-width: min(100%, 280px) !important;
        flex: 1 1 280px !important;
    }}
}}
</style>
"""


def apply_theme() -> None:
    """Inject project CSS overrides on top of .streamlit/config.toml.

    Call once per page, immediately after ``st.set_page_config()``.
    config.toml handles background, text colour, font, and primary accent.
    This function adds borders, label styles, and responsive breakpoints.
    """
    st.markdown(_OVERRIDE_CSS, unsafe_allow_html=True)


# ── Page header ────────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "") -> None:
    """Render a page title using native st.title + an optional subtitle.

    Parameters
    ----------
    title:
        Main heading, e.g. ``"Regional Job Market"``.
    subtitle:
        Muted secondary line shown below the title.
    """
    st.title(title)
    if subtitle:
        st.markdown(
            f"<p style='margin:-8px 0 16px;color:{SUBTEXT};font-size:0.9rem'>"
            f"{_html.escape(subtitle)}</p>",
            unsafe_allow_html=True,
        )


# ── KPI rows ───────────────────────────────────────────────────────────────────

def kpi_row(items: list[tuple[str, str]], columns: int | None = None) -> None:
    """Responsive KPI row using native ``st.metric`` inside ``st.columns``.

    This is the preferred helper for most pages. ``st.metric`` inherits
    theme colours from config.toml and the metric-container CSS override.
    The responsive column-wrap media query in ``apply_theme()`` handles
    stacking on narrow viewports.

    Parameters
    ----------
    items:
        List of ``(label, value)`` tuples.
    columns:
        Column count. Defaults to ``len(items)``.
    """
    n = columns or len(items)
    cols = st.columns(n)
    for col, (label, value) in zip(cols, items):
        with col:
            st.metric(label, value)


def kpi_row_html(
    items: list[tuple[str, str]],
    *,
    margin_bottom: int = 16,
) -> None:
    """KPI cards as a pure-HTML responsive grid (``dsj-kpi-grid`` CSS class).

    Use when you need centred text and custom font sizing that ``st.metric``
    doesn't produce. The grid adapts: 4 cols on desktop → 2 on tablet →
    1 on phone, driven by the media queries in ``apply_theme()``.

    Parameters
    ----------
    items:
        List of ``(label, value)`` tuples.
    margin_bottom:
        Gap below the grid in pixels.
    """
    n = len(items)
    cards = "".join(
        f'<div style="background:{SURFACE};border:1px solid {BORDER};'
        f'border-radius:8px;padding:12px 16px;text-align:center">'
        f'<div style="color:{SUBTEXT};font-size:0.78rem;margin-bottom:4px">'
        f'{_html.escape(lbl)}</div>'
        f'<div style="color:{TEXT};font-size:1.5rem;font-weight:600;line-height:1.2">'
        f'{_html.escape(val)}</div>'
        f'</div>'
        for lbl, val in items
    )
    st.markdown(
        f'<div class="dsj-kpi-grid" '
        f'style="--kpi-cols:{n};margin-bottom:{margin_bottom}px">'
        f'{cards}</div>',
        unsafe_allow_html=True,
    )


# ── Section divider ────────────────────────────────────────────────────────────

def section_divider(label: str = "") -> None:
    """Thin styled ``<hr>`` with an optional centred label.

    Parameters
    ----------
    label:
        Optional text centred on the rule.
    """
    if label:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;margin:16px 0">'
            f'<hr style="flex:1;border-color:{BORDER};margin:0">'
            f'<span style="color:{SUBTEXT};font-size:0.8rem;white-space:nowrap">'
            f'{_html.escape(label)}</span>'
            f'<hr style="flex:1;border-color:{BORDER};margin:0">'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<hr style="border-color:{BORDER}">', unsafe_allow_html=True)


# ── Empty state ────────────────────────────────────────────────────────────────

def empty_state(message: str = "No data matches the current filters.") -> None:
    """Centred empty-state message, consistent across all pages."""
    st.markdown(
        f'<div style="text-align:center;padding:48px 0;color:{SUBTEXT};font-size:1rem">'
        f'{_html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


# ── Badge / pill ───────────────────────────────────────────────────────────────

def badge(text: str, color: str = ACCENT_BLUE) -> str:
    """Return an inline HTML pill string for use inside ``st.markdown``.

    Parameters
    ----------
    text:
        Badge label.
    color:
        Accent colour — use the ``ACCENT_*`` constants.

    Example
    -------
    st.markdown(badge("Python", ACCENT_BLUE) + badge("AWS", ACCENT_AMBER),
                unsafe_allow_html=True)
    """
    return (
        f'<span style="display:inline-block;background:{color}22;'
        f'color:{color};border:1px solid {color}55;'
        f'border-radius:999px;padding:1px 10px;font-size:0.78rem;'
        f'font-family:{FONT};margin:2px">{_html.escape(text)}</span>'
    )
