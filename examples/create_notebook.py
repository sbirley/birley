"""Create a notebook and add sources to it.

Usage:
    python examples/create_notebook.py "My Research" https://example.com https://another.com

Requires authentication via `notebooklm login` first.
"""

import asyncio
import sys

from notebooklm import NotebookLMClient


async def main():
    if len(sys.argv) < 3:
        print("Usage: python examples/create_notebook.py <title> <url> [url ...]")
        sys.exit(1)

    title = sys.argv[1]
    urls = sys.argv[2:]

    async with await NotebookLMClient.from_storage() as client:
        print(f"Creating notebook: {title}")
        notebook = await client.notebooks.create(title)
        print(f"Created notebook: {notebook.id}")

        for url in urls:
            print(f"Adding source: {url}")
            source = await client.sources.add_url(notebook.id, url)
            print(f"  Added: {source.title} (id: {source.id})")

            print("  Waiting for processing...")
            ready = await client.sources.wait_until_ready(notebook.id, source.id)
            print(f"  Ready: {ready.title}")

        print(f"\nNotebook '{title}' is ready with {len(urls)} source(s).")
        print(f"Notebook ID: {notebook.id}")


if __name__ == "__main__":
    asyncio.run(main())
