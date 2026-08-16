"""
app.py — Router entry point (Streamlit Cloud "Main file path" stays
streamlit_app/app.py, unchanged, so no deployment settings need updating).

Uses st.navigation() to give every page an explicit, client-facing sidebar
label — this is what replaces the default "app" label (Streamlit otherwise
derives it from this file's name) with "Command Centre".
"""
import streamlit as st

from components.styling import inject_base_css, sidebar_nav_header

inject_base_css()
sidebar_nav_header()

pg = st.navigation([
    st.Page("views/enterprise.py", title="Command Centre", icon="🏢", default=True),
    st.Page("pages/1_Regional_Manager.py", title="Regional Manager", icon="🌍"),
    st.Page("pages/2_Store_Manager.py", title="Store Manager", icon="🏪"),
    st.Page("pages/3_CSCO.py", title="Head of Planning / CSCO", icon="📊"),
])
pg.run()
