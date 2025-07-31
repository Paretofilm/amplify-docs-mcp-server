#!/usr/bin/env python3
"""
Enhanced Amplify Documentation Scraper
Focuses on getting comprehensive frontend/UI documentation
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
from amplify_docs_server import AmplifyDocsScraper, AmplifyDocsDatabase

logger = logging.getLogger(__name__)

class EnhancedAmplifyDocsScraper(AmplifyDocsScraper):
    """Enhanced scraper that targets specific documentation areas."""
    
    def __init__(self):
        super().__init__()
        # Add additional URLs for comprehensive coverage
        self.additional_urls = [
            # UI Components
            "https://docs.amplify.aws/nextjs/build-ui/",
            "https://docs.amplify.aws/nextjs/build-ui/formbuilder/",
            "https://docs.amplify.aws/nextjs/build-ui/formbuilder/customize/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/databinding/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/eventhandling/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/slots/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/collections/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/responsive/",
            "https://docs.amplify.aws/nextjs/build-ui/uibuilder/override/",
            
            # Connected Components
            "https://ui.docs.amplify.aws/react/connected-components/authenticator",
            "https://ui.docs.amplify.aws/react/connected-components/storage/storageimage",
            "https://ui.docs.amplify.aws/react/connected-components/storage/storagemanager",
            "https://ui.docs.amplify.aws/react/connected-components/storage/fileuploader",
            "https://ui.docs.amplify.aws/react/connected-components/account-settings",
            "https://ui.docs.amplify.aws/react/connected-components/in-app-messaging",
            
            # Theming
            "https://ui.docs.amplify.aws/react/theming",
            "https://ui.docs.amplify.aws/react/theming/theme-provider",
            "https://ui.docs.amplify.aws/react/theming/css-variables",
            "https://ui.docs.amplify.aws/react/theming/dark-mode",
            "https://ui.docs.amplify.aws/react/theming/responsive",
            
            # All UI Components
            "https://ui.docs.amplify.aws/react/components/alert",
            "https://ui.docs.amplify.aws/react/components/badge",
            "https://ui.docs.amplify.aws/react/components/button",
            "https://ui.docs.amplify.aws/react/components/card",
            "https://ui.docs.amplify.aws/react/components/collection",
            "https://ui.docs.amplify.aws/react/components/divider",
            "https://ui.docs.amplify.aws/react/components/flex",
            "https://ui.docs.amplify.aws/react/components/grid",
            "https://ui.docs.amplify.aws/react/components/heading",
            "https://ui.docs.amplify.aws/react/components/icon",
            "https://ui.docs.amplify.aws/react/components/image",
            "https://ui.docs.amplify.aws/react/components/link",
            "https://ui.docs.amplify.aws/react/components/loader",
            "https://ui.docs.amplify.aws/react/components/menu",
            "https://ui.docs.amplify.aws/react/components/pagination",
            "https://ui.docs.amplify.aws/react/components/placeholder",
            "https://ui.docs.amplify.aws/react/components/rating",
            "https://ui.docs.amplify.aws/react/components/scrollview",
            "https://ui.docs.amplify.aws/react/components/searchfield",
            "https://ui.docs.amplify.aws/react/components/selectfield",
            "https://ui.docs.amplify.aws/react/components/sliderfield",
            "https://ui.docs.amplify.aws/react/components/stepperfield",
            "https://ui.docs.amplify.aws/react/components/switchfield",
            "https://ui.docs.amplify.aws/react/components/table",
            "https://ui.docs.amplify.aws/react/components/tabs",
            "https://ui.docs.amplify.aws/react/components/text",
            "https://ui.docs.amplify.aws/react/components/textareafield",
            "https://ui.docs.amplify.aws/react/components/textfield",
            "https://ui.docs.amplify.aws/react/components/togglebutton",
            "https://ui.docs.amplify.aws/react/components/view",
            
            # Guides
            "https://docs.amplify.aws/nextjs/how-amplify-works/",
            "https://docs.amplify.aws/nextjs/how-amplify-works/concepts/",
            "https://docs.amplify.aws/nextjs/build-a-backend/troubleshooting/",
            "https://docs.amplify.aws/nextjs/deploy-and-host/troubleshooting/",
            
            # API and Data
            "https://docs.amplify.aws/nextjs/build-a-backend/data/connect-to-API/",
            "https://docs.amplify.aws/nextjs/build-a-backend/data/customize-authz/",
            "https://docs.amplify.aws/nextjs/build-a-backend/data/data-modeling/",
            "https://docs.amplify.aws/nextjs/build-a-backend/data/working-with-files/",
            
            # Storage patterns
            "https://docs.amplify.aws/nextjs/build-a-backend/storage/upload/",
            "https://docs.amplify.aws/nextjs/build-a-backend/storage/download/",
            "https://docs.amplify.aws/nextjs/build-a-backend/storage/remove/",
            "https://docs.amplify.aws/nextjs/build-a-backend/storage/list/",
            "https://docs.amplify.aws/nextjs/build-a-backend/storage/copy/",
            "https://docs.amplify.aws/nextjs/build-a-backend/storage/get-properties/",
            
            # Deployment
            "https://docs.amplify.aws/nextjs/deploy-and-host/fullstack-branching/",
            "https://docs.amplify.aws/nextjs/deploy-and-host/custom-domains/",
            "https://docs.amplify.aws/nextjs/deploy-and-host/environment-variables/",
            "https://docs.amplify.aws/nextjs/deploy-and-host/monorepos/",
        ]
    
    def categorize_url(self, url: str) -> str:
        """Enhanced categorization for better organization."""
        path = url.lower()
        
        # More specific categorization
        if 'build-ui' in path or 'ui.docs.amplify' in path or '/components/' in path:
            return 'frontend'
        elif 'connected-components' in path:
            return 'connected-components'
        elif 'theming' in path:
            return 'theming'
        elif 'troubleshooting' in path:
            return 'troubleshooting'
        elif 'auth' in path or 'authentication' in path:
            return 'authentication'
        elif 'storage' in path:
            return 'storage'
        elif 'data' in path or 'api' in path or 'graphql' in path:
            return 'api-data'
        elif 'deploy' in path or 'host' in path:
            return 'deployment'
        elif 'start' in path or 'quickstart' in path:
            return 'getting-started'
        else:
            return super().categorize_url(url)
    
    async def scrape_enhanced_docs(self, save_markdown=True):
        """Scrape documentation with enhanced coverage."""
        db = AmplifyDocsDatabase()
        
        logger.info("Starting enhanced documentation scraping...")
        
        # First, scrape the base documentation
        await self.scrape_docs(force_refresh=False, save_markdown=save_markdown)
        
        # Then scrape additional URLs
        logger.info(f"Scraping {len(self.additional_urls)} additional URLs...")
        
        scraped_count = 0
        errors = 0
        
        for i, url in enumerate(self.additional_urls, 1):
            logger.info(f"Scraping additional {i}/{len(self.additional_urls)}: {url}")
            
            # Skip if already scraped
            if url in self.scraped_urls:
                logger.info(f"Already scraped: {url}")
                continue
            
            doc_data = await self.fetch_page(url)
            
            if doc_data:
                if db.save_document(doc_data):
                    scraped_count += 1
                    self.scraped_urls.add(url)
                else:
                    errors += 1
            else:
                errors += 1
            
            # Small delay to be respectful
            await asyncio.sleep(0.5)
        
        logger.info(f"Enhanced scraping completed! Added {scraped_count} new documents, {errors} errors.")
        
        # Update statistics
        stats = db.get_stats()
        logger.info(f"Total documents now: {stats.get('total_documents', 0)}")
        
        # Show category distribution
        logger.info("Category distribution:")
        for category, count in stats.get('categories', {}).items():
            logger.info(f"  {category}: {count}")
    
    async def fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Enhanced page fetching with better content extraction."""
        try:
            # Handle different documentation sites
            if 'ui.docs.amplify' in url:
                # UI documentation has different structure
                return await self.fetch_ui_docs_page(url)
            else:
                return await super().fetch_page(url)
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def fetch_ui_docs_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Special handler for UI documentation pages."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Extract title
                    title = "Untitled"
                    title_elem = soup.find('h1') or soup.find('h2') or soup.find('title')
                    if title_elem:
                        title = title_elem.get_text().strip()
                    
                    # Extract content - UI docs have different structure
                    content_elem = soup.find('main') or soup.find('article') or soup.find(class_='docs-content')
                    
                    if content_elem:
                        # Extract code examples
                        code_examples = []
                        for pre in content_elem.find_all('pre'):
                            code_examples.append(pre.get_text())
                        
                        # Convert to markdown
                        markdown_content = self.html_to_markdown(content_elem)
                        raw_content = content_elem.get_text(separator='\n', strip=True)
                        
                        # Add code examples section if found
                        if code_examples:
                            markdown_content += "\n\n## Code Examples\n\n"
                            for example in code_examples[:3]:  # Limit to 3 examples
                                markdown_content += f"```jsx\n{example}\n```\n\n"
                        
                        return {
                            'url': url,
                            'title': title,
                            'content': raw_content,
                            'markdown_content': markdown_content,
                            'category': self.categorize_url(url)
                        }
        except Exception as e:
            logger.error(f"Error fetching UI docs {url}: {e}")
            return None


async def main():
    """Run the enhanced scraper."""
    async with EnhancedAmplifyDocsScraper() as scraper:
        await scraper.scrape_enhanced_docs(save_markdown=True)
    
    # Regenerate the index with new content
    from doc_indexer import DocumentationIndexer
    indexer = DocumentationIndexer()
    index = indexer.generate_index()
    indexer.save_index()
    indexer.create_summary_table()
    
    print("\nEnhanced scraping complete! Documentation index has been updated.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())