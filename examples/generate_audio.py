"""Generate an Audio Overview (podcast) from a notebook and download it.

Usage:
    python examples/generate_audio.py <notebook_id> [output.mp3]

Requires authentication via `notebooklm login` first.
"""

import asyncio
import sys

from notebooklm import NotebookLMClient


async def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/generate_audio.py <notebook_id> [output.mp3]")
        sys.exit(1)

    notebook_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "output.mp3"

    async with await NotebookLMClient.from_storage() as client:
        print("Generating audio overview...")
        status = await client.artifacts.generate_audio(notebook_id)
        print(f"Generation started (task: {status.task_id})")

        print("Waiting for completion (this may take a few minutes)...")
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        print("Audio generation complete!")

        print(f"Downloading to {output_path}...")
        await client.artifacts.download_audio(notebook_id, output_path)
        print(f"Saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
