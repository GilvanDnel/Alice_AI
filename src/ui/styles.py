"""Custom CSS styles and responsive design system for Alice AI (WebAcademy Palette)."""

from __future__ import annotations

import streamlit as st

CUSTOM_CSS = """
<style>
/* 1. ABSOLUTE REMOVAL OF ALL CHAT AVATARS (No robot icon, no human icon) */
[data-testid="stChatMessageAvatar"],
div[data-testid="stChatMessageAvatar"],
.stChatMessageAvatar,
img[data-testid="stChatMessageAvatar"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    visibility: hidden !important;
    opacity: 0 !important;
}

div[data-testid="stChatMessage"] {
    padding-left: 0 !important;
    margin-bottom: 12px !important;
}

/* 2. FRAMED CONTAINER WINDOW (WebAcademy #0071bc clean theme) */
.main .block-container {
    max-width: 900px !important;
    border-radius: 14px !important;
    padding: 2rem 2.5rem 6rem 2.5rem !important;
    margin-top: 1.25rem !important;
    margin-bottom: 5rem !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05) !important;
    background-color: var(--secondary-background-color) !important;
}

/* 3. UNIFORM CATEGORY BUTTONS */
div[data-testid="column"] button {
    height: 52px !important;
    min-height: 52px !important;
    max-height: 52px !important;
    border-radius: 10px !important;
    font-size: 0.86rem !important;
    font-weight: 600 !important;
    border: 1px solid #e2e8f0 !important;
    background-color: var(--background-color) !important;
    color: var(--text-color) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    line-height: 1.2 !important;
    padding: 6px 10px !important;
    transition: all 0.2s ease-in-out !important;
}

div[data-testid="column"] button:hover {
    border-color: var(--primary-color, #0071bc) !important;
    background-color: var(--primary-color, #0071bc) !important;
    color: #FFFFFF !important;
    transform: translateY(-1px) !important;
}

/* 4. CLEAN CITATION BADGES (.badge-prisma inspired) */
.source-badge-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
    margin-bottom: 8px;
}

.source-badge {
    display: inline-flex;
    align-items: center;
    background-color: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 0.8rem;
    font-weight: 600;
}

/* 5. FIXED BOTTOM FOOTER LAYOUT */
div[data-testid="stBottom"] {
    bottom: 34px !important;
    background-color: transparent !important;
}

.app-footer-fixed {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 34px;
    background-color: var(--background-color);
    border-top: 1px solid #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    color: var(--text-color);
    opacity: 0.85;
    z-index: 9999;
}

.app-footer-fixed a {
    color: var(--primary-color, #0071bc);
    text-decoration: none;
    font-weight: 600;
    margin: 0 4px;
}

.app-footer-fixed a:hover {
    text-decoration: underline;
}

/* Mobile Responsiveness Rules */
@media (max-width: 768px) {
    .main .block-container {
        padding: 1.5rem 1rem 5.5rem 1rem !important;
        margin-top: 0.5rem !important;
        margin-bottom: 4.5rem !important;
        border-radius: 12px !important;
    }

    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
        margin-bottom: 8px !important;
    }

    div[data-testid="column"] button {
        height: 48px !important;
        min-height: 48px !important;
        max-height: 48px !important;
        font-size: 0.88rem !important;
    }
}
</style>
"""


def load_custom_css() -> None:
    """Inject custom executive & mobile responsive CSS rules."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)





