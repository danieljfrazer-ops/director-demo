from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
import websockets


class ComfyUIError(RuntimeError):
    """Raised for ComfyUI transport or workflow failures."""


@dataclass(frozen=True)
class GeneratedFile:
    filename: str
    subfolder: str
    kind: str
    node_id: str


class ComfyUIClient:
    """Small asynchronous client for the local ComfyUI queue and WebSocket API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client_id = str(uuid4())
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def __aenter__(self) -> ComfyUIClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def health(self) -> dict[str, Any]:
        response = await self._http.get("/system_stats")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def upload_image(self, path: Path, *, overwrite: bool = False) -> dict[str, Any]:
        with path.open("rb") as image:
            response = await self._http.post(
                "/upload/image",
                data={"overwrite": str(overwrite).lower(), "type": "input"},
                files={"image": (path.name, image)},
            )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def queue_prompt(self, workflow: dict[str, Any]) -> str:
        response = await self._http.post(
            "/prompt", json={"prompt": workflow, "client_id": self.client_id}
        )
        if response.is_error:
            raise ComfyUIError(f"ComfyUI rejected workflow: {response.text}")
        payload = response.json()
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI response had no prompt_id: {payload}")
        return str(prompt_id)

    async def events(self, prompt_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield JSON events for one prompt until execution completes."""
        async with websockets.connect(self._websocket_url()) as socket:
            async for raw in socket:
                if not isinstance(raw, str):
                    continue
                event: dict[str, Any] = json.loads(raw)
                data = event.get("data", {})
                event_prompt = data.get("prompt_id")
                if event_prompt not in {None, prompt_id}:
                    continue
                yield event
                if event.get("type") == "executing" and data.get("node") is None:
                    return
                if event.get("type") == "execution_error":
                    raise ComfyUIError(str(data))

    async def wait_for_files(
        self, prompt_id: str, *, history_retries: int = 10
    ) -> list[GeneratedFile]:
        async for _ in self.events(prompt_id):
            pass

        for attempt in range(history_retries):
            history = await self.history(prompt_id)
            if prompt_id in history:
                return self._extract_files(history[prompt_id])
            await asyncio.sleep(min(0.2 * 2**attempt, 2.0))
        raise ComfyUIError(f"Completed prompt {prompt_id} never appeared in history")

    async def run(self, workflow: dict[str, Any]) -> list[GeneratedFile]:
        prompt_id = await self.queue_prompt(workflow)
        return await self.wait_for_files(prompt_id)

    async def history(self, prompt_id: str) -> dict[str, Any]:
        response = await self._http.get(f"/history/{prompt_id}")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def download(self, generated: GeneratedFile, destination: Path) -> Path:
        query = urlencode(
            {
                "filename": generated.filename,
                "subfolder": generated.subfolder,
                "type": generated.kind,
            }
        )
        response = await self._http.get(f"/view?{query}")
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        return destination

    def _websocket_url(self) -> str:
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunparse((scheme, parsed.netloc, "/ws", "", f"clientId={self.client_id}", ""))

    @staticmethod
    def _extract_files(record: dict[str, Any]) -> list[GeneratedFile]:
        files: list[GeneratedFile] = []
        for node_id, output in record.get("outputs", {}).items():
            for collection_name in ("images", "gifs", "videos", "audio"):
                for item in output.get(collection_name, []):
                    if "filename" not in item:
                        continue
                    files.append(
                        GeneratedFile(
                            filename=item["filename"],
                            subfolder=item.get("subfolder", ""),
                            kind=item.get("type", "output"),
                            node_id=str(node_id),
                        )
                    )
        return files
