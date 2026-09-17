import pytest

from director_demo.comfy import ComfyUIClient, ComfyUIError, GeneratedFile


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8188", "http://localhost:8188", "http://[::1]:8188"],
)
def test_client_accepts_loopback_urls(url: str) -> None:
    client = ComfyUIClient(url)
    assert client.base_url == url


def test_client_rejects_remote_url_by_default() -> None:
    with pytest.raises(ComfyUIError, match="Remote ComfyUI URLs"):
        ComfyUIClient("http://render.example:8188")


@pytest.mark.parametrize(
    ("filename", "subfolder"),
    [
        ("../secret", ""),
        ("/tmp/secret", ""),
        ("..\\secret", ""),
        ("clip.mp4", "../outside"),
        ("clip.mp4", "/tmp"),
        ("clip.mp4", "..\\outside"),
    ],
)
def test_generated_file_rejects_unsafe_server_paths(filename: str, subfolder: str) -> None:
    with pytest.raises(ComfyUIError, match="Unsafe generated"):
        GeneratedFile(filename=filename, subfolder=subfolder, kind="output", node_id="1")


def test_generated_file_rejects_unknown_storage_type() -> None:
    with pytest.raises(ComfyUIError, match="Unexpected generated file type"):
        GeneratedFile(filename="clip.mp4", subfolder="", kind="remote", node_id="1")
