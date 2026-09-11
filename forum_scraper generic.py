# forum_scraper.py - Complete Forum Thread Post Scraper
# Version: 2026-01-17 15:30
## remember to add the details of the URL and target member ID under "Default_config"
import asyncio
import os
import re
import json
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Page

# ==================== VERSION HEADER ====================
version_date = datetime.now()
print(f"# Version: {version_date.strftime('%Y-%m-%d %H:%M')}")

# ==================== CONFIGURATION ====================
class Config:
    """Stores and validates configuration inputs."""
    
    def __init__(self):
        self._thread_url = ""
        self._target_member_id = ""
        self._minimum_word_count = 0
    
    @property
    def thread_url(self):
        return self._thread_url
    
    @thread_url.setter
    def thread_url(self, value):
        if not value or not isinstance(value, str) or not value.startswith("http"):
            raise ValueError("Must be a valid HTTP URL")
        self._thread_url = value
    
    @property
    def target_member_id(self):
        return self._target_member_id
    
    @target_member_id.setter
    def target_member_id(self, value):
        if not isinstance(value, (int, str)) or len(str(value).strip()) == 0:
            raise ValueError("Must be a numeric member ID")
        self._target_member_id = str(value)
    
    @property
    def minimum_word_count(self):
        return self._minimum_word_count
    
    @minimum_word_count.setter
    def minimum_word_count(self, value):
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError("Must be a non-negative number")
        self._minimum_word_count = int(value)

# Default configuration for testing (Citation 2 & 3) - UPDATED TO 200
DEFAULT_CONFIG = Config()
DEFAULT_CONFIG.thread_url = "URL here"
DEFAULT_CONFIG.target_member_id = "MEMBERID HERE"
DEFAULT_CONFIG.minimum_word_count = 200

# ==================== BROWSER FETCHER ====================
class BrowserFetcher:
    """Responsible for Playwright startup and page navigation."""
    
    def __init__(self):
        self.browser = None
        self.page = None
    
    async def start(self, headless=True):
        """Start browser context (persistent if needed)."""
        print("Starting browser...")
        try:
            self.browser = await async_playwright().start()
            
            # Use persistent context for session persistence (Citation 2)
            self.browser = await self.browser.chromium.launch_persistent_context(
                user_data_dir="browser_profile",
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            
            self.page = await self.browser.new_page()
        except Exception as e:
            print(f"Browser startup error: {e}")
            raise
    
    async def navigate(self, url):
        """Navigate to URL and wait for load with retry."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.page.goto(url)
                await self.page.wait_for_load_state("networkidle")
                print(f"Page loaded successfully (Attempt {attempt + 1})")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Connection issue on attempt {attempt + 1}: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"All retries failed after {max_retries} attempts")
                    raise
    
    async def close(self):
        """Graceful shutdown."""
        if self.browser:
            await self.browser.close()

# Singleton instance
browser_fetcher = BrowserFetcher()

# ==================== FORUM PARSER ====================
class ForumParser:
    """Responsible for extracting post containers, authors, text."""
    
    @staticmethod
    async def extract_posts(page: Page):
        """Extract all post containers from current page (Citation 2 Step 6)."""
        posts = await page.query_selector_all('table.tborder[id^="post"]')
        return posts
    
    @staticmethod
    async def get_author_member_id(post_element, target_member_id: str) -> bool:
        """Identify author/member ID and compare to configured member ID (Citation 3)."""
        author_elem = await post_element.query_selector('a.bigusername')
        
        if not author_elem:
            return False
        
        href = await author_elem.get_attribute("href")
        
        # Extract the author member ID from its href (e.g., u=411883)
        match = re.search(r'u=(\d+)', href)
        if not match:
            return False
        
        post_member_id = match.group(1)
        return post_member_id == target_member_id
    
    @staticmethod
    async def extract_post_text(post_element):
        """Extract the post text from message container (Citation 3)."""
        message_elem = await post_element.query_selector('div[id^="post_message_"]')
        
        if not message_elem:
            return ""
        
        # Extract visible text while preserving paragraph/line breaks
        text = await message_elem.inner_text()
        return text
    
    @staticmethod
    def count_words(text):
        """Deterministic word-count function (Citation 3)."""
        return len(re.findall(r"[\w'’-]+", text))
    
    @staticmethod
    async def find_next_page(page: Page) -> bool:
        """Find next-page link for pagination (Citation 2 Step 8)."""
        next_btn = await page.query_selector('a[rel="next"]')
        return next_btn is not None

# ==================== OUTPUT MANAGER ====================
class OutputManager:
    """Responsible for creating output directories and saving files."""
    
    def __init__(self, thread_url: str):
        self.thread_identifier = self._sanitize_identifier(thread_url)
        self.output_dir = f"output/{self.thread_identifier}"
        self.posts_dir = os.path.join(self.output_dir, "posts")
        self.config_log_path = os.path.join(self.output_dir, "run_config.json")
    
    @staticmethod
    def _sanitize_identifier(url):
        """Create a safe folder name from the URL."""
        return re.sub(r'[^a-zA-Z0-9]', '_', url.split('?')[0])
    
    async def create_directories(self):
        """Create output directories if they don't exist."""
        os.makedirs(self.posts_dir, exist_ok=True)
    
    async def save_post(self, post_id: str, text: str, sequence_num: int, page_url: str, word_count: int):
        """Save individual post to file with metadata (Citation 1)."""
        # New format: sequence_num_wordcount_postid.txt (e.g., 047_350_16738460.txt)
        filename = f"{sequence_num:03d}_{word_count:03d}_{post_id}.txt"
        filepath = os.path.join(self.posts_dir, filename)
        
        # Add page URL as first line for debugging (Your adjustment - Citation 1)
        header = f"# Page URL: {page_url}\n\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + text)
        
        return filepath
    
    async def create_combined_file(self, posts_dir):
        """Create combined.txt from all individual files (Citation 1)."""
        combined_path = os.path.join(self.output_dir, "combined.txt")
        
        with open(combined_path, "w", encoding="utf-8") as f:
            for root, dirs, files in os.walk(posts_dir):
                for file in sorted(files):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as src:
                        content = src.read()
                        if content:
                            f.write(content + "\n\n")
        
        return combined_path
    
    async def save_config_log(self, config):
        """Save run configuration for metadata (Citation 2 Step 14)."""
        log_data = {
            "thread_url": config.thread_url,
            "target_member_id": config.target_member_id,
            "minimum_word_count": config.minimum_word_count,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.config_log_path, "w") as f:
            json.dump(log_data, f, indent=2)

# ==================== SCRAPE CONTROLLER ====================
class ScrapeController:
    """Responsible for pagination loop and duplicate prevention."""
    
    def __init__(self):
        self.posts_found = 0
        self.sequence_num = 0
        self.pages_scanned = 0
    
    async def run(self, config: Config):
        """Main scraping workflow (Citation 2)."""
        
        # Create output manager
        output_manager = OutputManager(config.thread_url)
        await output_manager.create_directories()
        
        # Start browser and navigate to thread
        await browser_fetcher.start(headless=True)
        await browser_fetcher.navigate(config.thread_url)
        
        parser = ForumParser()
        controller = self
        
        while True:
            self.pages_scanned += 1
            
            posts = await parser.extract_posts(browser_fetcher.page)
            
            # Progress logging (Citation 1 Section 11)
            matching_count = 0
            skipped_word_count = 0
            
            for post in posts:
                self.posts_found += 1
                
                # Check author match (Citation 2 Step 7c)
                if not await parser.get_author_member_id(post, config.target_member_id):
                    continue
                
                # Extract and count words (Citation 3)
                text = await parser.extract_post_text(post)
                word_count = parser.count_words(text)
                
                # Filter by minimum word count (Citation 2 Step 7h)
                if word_count <= config.minimum_word_count:
                    skipped_word_count += 1
                    continue
                
                matching_count += 1
                
                # Save qualifying post with page URL and word count metadata (Your adjustment)
                controller.sequence_num += 1
                current_page_url = browser_fetcher.page.url
                filepath = await output_manager.save_post(
                    post_id=controller.sequence_num,
                    text=text,
                    sequence_num=controller.sequence_num,
                    page_url=current_page_url,
                    word_count=word_count
                )
                
                print(f"[OK] Saved post #{controller.sequence_num} (Words: {word_count}) to {filepath}")
            
            # Progress summary per page (Citation 1 Section 11)
            if matching_count > 0 or skipped_word_count > 0:
                print(f"\nPage {self.pages_scanned}:")
                print(f"  Posts found: {len(posts)}")
                print(f"  Matching member: {matching_count}")
                print(f"  Saved: {matching_count}")
                print(f"  Skipped for word count: {skipped_word_count}")
            
            # Check for next page (Citation 2 Step 8-9)
            if await parser.find_next_page(browser_fetcher.page):
                print("\nFollowing next page...")
                await browser_fetcher.page.click('a[rel="next"]')
                await browser_fetcher.page.wait_for_load_state("networkidle")
            else:
                print("\n--- Scrape Complete ---")
                break
        
        # Save final config log (Citation 2 Step 14)
        await output_manager.save_config_log(config)
        
        await browser_fetcher.close()

# ==================== MAIN ENTRY POINT ====================
async def main():
    """Entry point with configuration loading."""
    
    # Load configuration (can be modified for testing - Citation 3)
    config = DEFAULT_CONFIG
    
    print(f"Starting scrape of: {config.thread_url}")
    print(f"Target Member ID: {config.target_member_id}")
    print(f"Minimum Word Count: {config.minimum_word_count}")
    print("-" * 50)
    
    controller = ScrapeController()
    await controller.run(config)
    
    # ==================== COMBINE FILES PROMPT (Your adjustment) ====================
    output_manager = OutputManager(DEFAULT_CONFIG.thread_url)
    combined_path = os.path.join(output_manager.output_dir, "combined.txt")
    
    print("\n" + "=" * 50)
    print("SCRAPE COMPLETE!")
    print("=" * 50)
    print(f"\nOutput Directory: {output_manager.output_dir}")
    if os.listdir(output_manager.posts_dir):
        print(f"Individual Files: {len(os.listdir(output_manager.posts_dir))} files found")
    else:
        print("Individual Files: No qualifying posts found")
    print(f"Combined File Path: {combined_path}")
    
    # Prompt user to combine files (Your adjustment - Citation 1)
    response = input("\nWould you like to combine all posts into a single file? (y/n): ").strip().lower()
    
    if response == 'y':
        print("Combining files...")
        await output_manager.create_combined_file(output_manager.posts_dir)
        print(f"Combined file created: {combined_path}")
    else:
        print("Files kept separate. You can manually combine them later.")

if __name__ == "__main__":
    asyncio.run(main())
