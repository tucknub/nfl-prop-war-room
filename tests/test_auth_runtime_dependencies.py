def test_streamlit_oidc_runtime_dependencies_importable() -> None:
    import httpx
    from authlib.integrations import starlette_client

    assert httpx is not None
    assert starlette_client is not None
