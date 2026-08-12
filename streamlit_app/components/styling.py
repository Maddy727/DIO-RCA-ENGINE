"""
styling.py

£ formatting, persona color identities, and shared CSS. No business logic.
"""
from __future__ import annotations

import streamlit as st

PERSONA_COLORS = {
    "enterprise": "#1B2A4A",   # deep navy — control tower / neutral executive
    "regional": "#B36A00",     # amber/orange
    "store": "#0B5AA8",        # blue
    "csco": "#1B6B3A",         # green
}

FONT_STACK = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"


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
    return f"{value:.1f}d"


def inject_base_css():
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: {FONT_STACK};
        }}
        .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }}
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        .kpi-card {{
            background: #FFFFFF;
            border: 1px solid #E4E7EC;
            border-radius: 10px;
            padding: 16px 18px;
            box-shadow: 0 1px 2px rgba(16,24,40,0.04);
        }}
        .kpi-label {{
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            color: #667085;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 26px;
            font-weight: 700;
            color: #101828;
            line-height: 1.1;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: #98A2B3;
            margin-top: 4px;
        }}
        .section-header {{
            font-size: 15px;
            font-weight: 700;
            color: #101828;
            margin: 22px 0 8px 0;
            padding-bottom: 6px;
            border-bottom: 2px solid #E4E7EC;
        }}
        .priority-badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            color: white;
            letter-spacing: 0.02em;
        }}
        .persona-banner {{
            padding: 18px 24px;
            border-radius: 12px;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(16,24,40,0.12);
        }}
        .persona-banner h2 {{
            margin: 0;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.01em;
        }}
        .persona-banner p {{
            margin: 4px 0 0 0;
            font-size: 14px;
            opacity: 0.85;
            font-style: italic;
        }}
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
        </style>
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
