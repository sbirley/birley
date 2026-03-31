"""Interactive chat with a NotebookLM notebook.

Usage:
    python examples/chat_with_notebook.py <notebook_id>

Type questions at the prompt. Type 'quit' or Ctrl+C to exit.
Requires authentication via `notebooklm login` first.
"""

import asyncio
import sys

from notebooklm import NotebookLMClient


async def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/chat_with_notebook.py <notebook_id>")
        sys.exit(1)

    notebook_id = sys.argv[1]
    conversation_id = None

    async with await NotebookLMClient.from_storage() as client:
        # Verify notebook exists
        notebooks = await client.notebooks.list()
        match = [nb for nb in notebooks if nb.id == notebook_id]
        if not match:
            print(f"Notebook {notebook_id} not found.")
            sys.exit(1)

        print(f"Chatting with: {match[0].title}")
        print("Type 'quit' to exit.\n")

        while True:
            try:
                question = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not question or question.lower() == "quit":
                break

            result = await client.chat.ask(
                notebook_id, question, conversation_id=conversation_id
            )
            conversation_id = result.conversation_id
            print(f"\nNotebook: {result.answer}\n")


if __name__ == "__main__":
    asyncio.run(main())
