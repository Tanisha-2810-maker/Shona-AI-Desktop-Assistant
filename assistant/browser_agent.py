from assistant.ai_brain import ask_ai
from system.browser import search_web_and_collect


def search_and_summarize(query: str) -> str:
    search_data = search_web_and_collect(query)

    prompt = f"""
You are Shona, an AI desktop assistant.

The user searched the web for:

{search_data["query"]}

Below is text extracted from the visible search-results page:

{search_data["text"]}

Provide:

1. A short direct answer to the search.
2. The main useful results or findings.
3. Important cautions if the results appear incomplete.
4. Suggested next steps when appropriate.

Do not invent URLs, names, prices, dates or claims that do not
appear in the extracted text.

Clearly mention when the search-result text is insufficient.
"""

    return ask_ai(prompt)