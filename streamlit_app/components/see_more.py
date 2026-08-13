"""
see_more.py

Small reusable "See more" / "See less" toggle, backed by session_state.
Used to show top-10 charts by default with an expand option, per instructions
#9/#10 (Enterprise Store DIO Variance, Regional Store DIO Ranking, and the
new Top 10 SKUs by DIO Variance charts on all three persona pages).
"""
from __future__ import annotations

import streamlit as st


def see_more_toggle(key: str, default_n: int = 10) -> int | None:
    """
    Renders a "See more" / "See less" button. Returns None when expanded
    (caller should show the full list) or default_n when collapsed
    (caller should show only the top default_n rows).
    """
    state_key = f"see_more_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False  # False = collapsed (top N)

    expanded = st.session_state[state_key]
    label = "See less" if expanded else "See more"
    if st.button(label, key=f"btn_{state_key}"):
        st.session_state[state_key] = not expanded
        st.rerun()

    return None if expanded else default_n
