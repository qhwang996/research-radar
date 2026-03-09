"""
NDSS Conference Paper Crawler
"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path


class NDSSCrawler:
    def __init__(self, year=2025):
        self.year = year
        self.base_url = f"https://www.ndss-symposium.org/ndss{year}/accepted-papers/"

    def fetch_papers(self):
        """Fetch accepted papers from NDSS"""
        print(f"Fetching NDSS {self.year} papers...")

        response = requests.get(self.base_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        # Find all paper entries
        paper_entries = soup.find_all('div', class_='pt-cv-content-item')
        
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
            title_elem = entry.find('h2', class_='pt-cv-title')
            if not title_elem:
                return None
            
            title_link = title_elem.find('a')
            title = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)
            paper_url = title_link.get('href', '') if title_link else ''
            
            # Extract authors
            authors = []
            author_div = entry.find('div', class_='pt-cv-ctf-value')
            if author_div:
                author_p = author_div.find('p')
                if author_p:
                    author_text = author_p.get_text(strip=True)
                    # Split by comma and clean
                    authors = [a.strip() for a in author_text.split(',')]
            
            return {
                'title': title,
                'authors': authors,
                'paper_url': paper_url,
                'conference': f'NDSS {self.year}',
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
        filename = f"{output_dir}/ndss_{self.year}_{timestamp}.json"
        
        data = {
            'source': 'NDSS',
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
    crawler = NDSSCrawler(year=2025)
    papers = crawler.fetch_papers()
    crawler.save_papers(papers)


if __name__ == '__main__':
    main()
