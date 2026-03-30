"""
LinkedIn HubSpot News Poster
-----------------------------
Fetches the latest HubSpot news using Claude (with web search),
generates a professional LinkedIn post, and publishes it via the LinkedIn API.

Schedule with cron to run daily at 5pm:
    0 17 * * * /usr/bin/python3 /path/to/linkedin_poster.py >> /var/log/linkedin_poster.log 2>&1
"""

import os
import json
import logging
import requests
from dotenv import load_dotenv
import anthropic

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

LINKEDIN_ACCESS_TOKEN = os.environ["LINKEDIN_ACCESS_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


def get_linkedin_person_id() -> str:
    """Retrieve the authenticated user's LinkedIn person URN."""
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.get(f"{LINKEDIN_API_BASE}/userinfo", headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    sub = data.get("sub")
    if not sub:
        raise ValueError(f"Could not retrieve LinkedIn person ID. Response: {data}")
    return sub


def generate_linkedin_post() -> str:
    """Use Claude with web search to find HubSpot news and generate a LinkedIn post."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    logger.info("Generating LinkedIn post about HubSpot news via Claude...")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": (
                    "Search for the latest HubSpot news from today or this week. "
                    "Then write a compelling LinkedIn post (150–250 words) about the most "
                    "interesting or impactful story you find. "
                    "The post should:\n"
                    "- Start with a strong hook\n"
                    "- Summarise the key news\n"
                    "- Include a brief insight or takeaway for marketing/sales professionals\n"
                    "- End with a relevant question to drive engagement\n"
                    "- Include 3–5 relevant hashtags at the end\n"
                    "Return ONLY the post text, nothing else."
                ),
            }
        ],
    )

    # Extract the final text response
    post_text = ""
    for block in response.content:
        if block.type == "text":
            post_text += block.text

    if not post_text.strip():
        raise ValueError("Claude returned an empty post.")

    logger.info("Post generated successfully.")
    return post_text.strip()


def publish_to_linkedin(person_id: str, post_text: str) -> dict:
    """Publish a text post to LinkedIn using the UGC Posts API."""
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    payload = {
        "author": f"urn:li:person:{person_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": post_text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    response = requests.post(
        f"{LINKEDIN_API_BASE}/ugcPosts",
        headers=headers,
        data=json.dumps(payload),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def main():
    logger.info("Starting LinkedIn HubSpot News Poster...")

    # Step 1: Get LinkedIn person ID
    logger.info("Fetching LinkedIn person ID...")
    person_id = get_linkedin_person_id()
    logger.info(f"LinkedIn person ID: {person_id}")

    # Step 2: Generate post content via Claude
    post_text = generate_linkedin_post()
    logger.info(f"Post preview:\n{post_text[:200]}...")

    # Step 3: Publish to LinkedIn
    logger.info("Publishing post to LinkedIn...")
    result = publish_to_linkedin(person_id, post_text)
    post_id = result.get("id", "unknown")
    logger.info(f"Post published successfully. Post ID: {post_id}")


if __name__ == "__main__":
    main()
