"""本地 .env 与 Streamlit Cloud Secrets 统一注入 os.environ。"""

from __future__ import annotations

import os


def bootstrap_env() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    try:
        import streamlit as st

        for key, value in dict(st.secrets).items():
            if isinstance(value, str):
                os.environ.setdefault(key, value)
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, str):
                        os.environ.setdefault(k, v)
    except Exception:
        pass
