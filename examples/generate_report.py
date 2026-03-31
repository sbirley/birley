"""Generate a report from a notebook and save it.

Usage:
    python examples/generate_report.py <notebook_id> [output.md]

Requires authentication via `notebooklm login` first.
"""

import asyncio
import sys

from notebooklm import NotebookLMClient


async def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/generate_report.py <notebook_id> [output.md]")
        sys.exit(1)

    notebook_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "report.md"

    async with await NotebookLMClient.from_storage() as client:
        print("Generating report...")
        status = await client.artifacts.generate_report(notebook_id)
        print(f"Generation started (task: {status.task_id})")

        print("Waiting for completion...")
        await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        print("Report generation complete!")

        print(f"Downloading to {output_path}...")
        await client.artifacts.download_report(notebook_id, output_path)
        print(f"Saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
