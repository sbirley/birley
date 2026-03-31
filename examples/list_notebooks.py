"""List all NotebookLM notebooks and their sources.

Usage:
    python examples/list_notebooks.py

Requires authentication via `notebooklm login` first.
"""

import asyncio

from notebooklm import NotebookLMClient


async def main():
    async with await NotebookLMClient.from_storage() as client:
        notebooks = await client.notebooks.list()

        if not notebooks:
            print("No notebooks found.")
            return

        print(f"Found {len(notebooks)} notebook(s):\n")
        for nb in notebooks:
            print(f"  [{nb.id}] {nb.title}")

            sources = await client.sources.list(nb.id)
            if sources:
                for src in sources:
                    if src.is_processing:
                        status = " (processing)"
                    elif src.is_error:
                        status = " (error)"
                    else:
                        status = ""
                    print(f"    - {src.title} [{src.kind}]{status}")
            else:
                print("    (no sources)")
            print()


if __name__ == "__main__":
    asyncio.run(main())
