"""
IEEE S&P (Oakland) Conference Paper Crawler
"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path


class SPCrawler:
    def __init__(self, year=2026):
        self.year = year
        self.base_url = f"https://sp{year}.ieee-security.org/accepted-papers.html"

    def fetch_papers(self):
        """Fetch accepted papers from S&P"""
        print(f"Fetching S&P {self.year} papers...")

        response = requests.get(self.base_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        # Find all paper entries
        paper_entries = soup.find_all('div', class_='list-group-item')

        for entry in paper_entries:
            paper = self._parse_paper(entry)
            if paper:
                papers.append(paper)

        print(f"Found {len(papers)} papers")
        return papers

    def _parse_paper(self, entry):
        """Parse a single paper entry"""
        try:
            # Extract title
            title_link = entry.find('a', {'data-toggle': 'collapse'})
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            # Remove the chevron icon text
            title = title.replace('☰', '').strip()
            
            # Extract authors
            authors = []
            author_div = entry.find('div', class_='authorlist')
            if author_div:
                author_text = author_div.get_text(strip=True)
                # Simple parsing - split by comma
                authors = [a.strip() for a in author_text.split(',') if a.strip()]
            
            return {
                'title': title,
                'authors': authors,
                'conference': f'IEEE S&P {self.year}',
                'year': self.year,
                'source_url': self.base_url
            }
        except Exception as e:
            print(f"Error parsing paper: {e}")
            return None

    def save_papers(self, papers, output_dir='data/raw/papers'):
        """Save papers to JSON file"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/sp_{self.year}_{timestamp}.json"
        
        data = {
            'source': 'IEEE S&P',
            'year': self.year,
            'fetched_at': datetime.now().isoformat(),
            'url': self.base_url,
            'total_papers': len(papers),
            'papers': papers
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved to {filename}")
        return filename


def main():
    crawler = SPCrawler(year=2026)
    papers = crawler.fetch_papers()
    crawler.save_papers(papers)


if __name__ == '__main__':
    main()
