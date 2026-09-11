# forum_scraper
Simple tool to search for posts from an author, extract it into a text doc. Created to help me track posts from trolls and submit for reporting. 

# Forum Thread Post Scraper

A configurable Python application that scans vBulletin-style forum threads, identifies posts by a specific member, and saves only posts exceeding a minimum word count.

## Installation

1. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   python -m playwright install chromium

run: python forum_scraper.py

output:
output/
  <thread_identifier>/
    posts/
      001_1370_16738460.txt   # Post 1, 1370 words, ID 16738460
      002_1304_16738475.txt   # Post 2, 1304 words, ID 16738475
      ...
    combined.txt              # All posts concatenated with separators
    run_config.json           # Metadata including word count thresholds

    
