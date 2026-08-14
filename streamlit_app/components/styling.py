"""
styling.py

£ formatting, persona color identities, chart color system, priority
label/dot treatment, Tesco text-based branding, and shared CSS. No
business logic — presentation only.
"""
from __future__ import annotations

import streamlit as st

PERSONA_COLORS = {
    "enterprise": "#1B2A4A",   # deep navy — control tower / neutral executive
    "regional": "#B36A00",     # amber/orange
    "store": "#0B5AA8",        # blue
    "csco": "#1B6B3A",         # green
}

# Vibrant-but-professional chart palette, used consistently across all
# charts rather than random per-chart color assignment (per instruction #19).
CHART_PALETTE = {
    "primary": "#0B5AA8",       # blue — general bars, DIO actual
    "primary_light": "#8FB8E0",
    "secondary": "#1B6B3A",     # green — positive/on-target
    "accent_amber": "#D97B0A",  # amber — warning/regional
    "accent_red": "#C81E3A",    # red — critical/excess/variance
    "neutral": "#98A2B3",       # muted grey — target/baseline reference
    "problem_area": {
        "Demand": "#0B5AA8",
        "Supply": "#D97B0A",
        "Network": "#1B6B3A",
        "Others": "#98A2B3",
    },
    "variance_scale": ["#FDECEA", "#F9B8AE", "#F08A76", "#E35B45", "#C81E3A", "#8E1029"],
}

FONT_STACK = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"

BRAND_NAME = "Tesco"
BRAND_TAGLINE = "DIO Control Tower"


def format_gbp(value: float) -> str:
    """£1,250 / £125k / £2.4m — UK retail convention."""
    if value is None:
        return "£0"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        return f"{sign}£{value / 1_000_000:.1f}m"
    if value >= 100_000:
        return f"{sign}£{value / 1_000:.0f}k"
    if value >= 1_000:
        return f"{sign}£{value / 1_000:.1f}k"
    return f"{sign}£{value:,.0f}"


def format_days(value: float) -> str:
    if value is None:
        return "0.0d"
    return f"{value:.1f}d"


def format_variance_days(value: float) -> str:
    """+16.4d / -3.2d — signed, for variance displays."""
    if value is None:
        return "0.0d"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}d"


def format_shelf_life(value: float, is_perishable) -> str:
    """
    Shelf Life Remaining is only meaningful for perishable SKUs — non-
    perishable rows carry a 999 sentinel (S22_Shelf_Life_Remaining_Days'
    "not applicable" placeholder, per the engine's own convention) which
    must never be displayed as if it were a real day count. Shows '-' for
    non-perishable (per your instruction), not 'N/A'.
    """
    perishable = is_perishable == 1 or is_perishable is True
    if not perishable or value is None or value >= 999:
        return "-"
    if value <= 0:
        return f"Expired ({value:.1f}d)"
    return f"{value:.1f}d"


def format_count(value) -> str:
    if value is None:
        return "0"
    return f"{value:,.0f}"


def inject_base_css():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: {FONT_STACK};
        }}
        .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1440px;
        }}
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* --- Brand strip --- */
        .brand-strip {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 2px 14px 2px;
            border-bottom: 1px solid #E4E7EC;
            margin-bottom: 14px;
        }}
        .brand-strip .brand-name {{
            font-weight: 800;
            font-size: 15px;
            color: #00539F;
            letter-spacing: -0.01em;
        }}
        .brand-strip .brand-tagline {{
            font-size: 12px;
            color: #98A2B3;
            font-weight: 500;
        }}

        /* --- KPI cards --- */
        .kpi-card {{
            background: #FFFFFF;
            border: 1px solid #E4E7EC;
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 1px 3px rgba(16,24,40,0.06);
            transition: box-shadow 0.15s ease;
        }}
        .kpi-card.kpi-primary {{
            border-top: 3px solid #0B5AA8;
        }}
        .kpi-label {{
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: #667085;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 27px;
            font-weight: 800;
            color: #101828;
            line-height: 1.1;
            letter-spacing: -0.02em;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: #98A2B3;
            margin-top: 4px;
        }}

        /* --- Section headers --- */
        .section-header {{
            font-size: 16px;
            font-weight: 800;
            color: #101828;
            margin: 26px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #E4E7EC;
            letter-spacing: -0.01em;
        }}
        .section-subtext {{
            font-size: 13px;
            color: #667085;
            margin: -8px 0 12px 0;
        }}

        /* --- Priority badge + dot --- */
        .priority-badge {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            color: white;
            letter-spacing: 0.02em;
        }}
        .priority-dot {{
            display: inline-block;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            margin-right: 6px;
            vertical-align: middle;
        }}
        .priority-label-inline {{
            font-weight: 700;
            font-size: 13px;
            vertical-align: middle;
        }}

        /* --- Persona banner --- */
        .persona-banner {{
            padding: 18px 24px;
            border-radius: 12px;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 4px 14px rgba(16,24,40,0.14);
        }}
        .persona-banner h2 {{
            margin: 0;
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.01em;
        }}
        .persona-banner p {{
            margin: 4px 0 0 0;
            font-size: 14px;
            opacity: 0.88;
            font-style: italic;
        }}

        /* --- FYI strip --- */
        .fyi-strip {{
            background: #F2F4F7;
            border: 1px dashed #98A2B3;
            border-radius: 10px;
            padding: 12px 16px;
            margin-top: 10px;
        }}
        .fyi-strip .fyi-title {{
            font-size: 12px;
            font-weight: 700;
            color: #475467;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 6px;
        }}

        /* --- Chart container --- */
        .chart-card {{
            background: #FFFFFF;
            border: 1px solid #E4E7EC;
            border-radius: 12px;
            padding: 14px 16px 4px 16px;
            margin-bottom: 8px;
        }}

        /* --- Empty state --- */
        .empty-state {{
            background: #F9FAFB;
            border: 1px dashed #D0D5DD;
            border-radius: 10px;
            padding: 24px;
            text-align: center;
            color: #667085;
            font-size: 14px;
            font-weight: 500;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand_strip():
    st.markdown(
        f"""
        <div class="brand-strip">
            <span class="brand-name">{BRAND_NAME}</span>
            <span class="brand-tagline">· {BRAND_TAGLINE}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def persona_banner(title: str, subtitle: str, color: str):
    st.markdown(
        f"""
        <div class="persona-banner" style="background:{color};">
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def priority_badge_html(label: str, color: str) -> str:
    return f'<span class="priority-badge" style="background:{color};">{label}</span>'


def priority_dot_label_html(label: str, color: str) -> str:
    """Small coloured dot immediately before the Priority Label text, per instruction #24."""
    return (
        f'<span class="priority-dot" style="background:{color};"></span>'
        f'<span class="priority-label-inline" style="color:{color};">{label}</span>'
    )


def empty_state_message(text: str = "No data available for the selected combination"):
    st.markdown(f'<div class="empty-state">{text}</div>', unsafe_allow_html=True)
