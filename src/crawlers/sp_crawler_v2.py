"""
IEEE S&P (Oakland) Conference Paper Crawler - Multi-year support
"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path


class SPCrawler:
    def __init__(self, years=None):
        """
        Args:
            years: list of years to crawl, e.g. [2024, 2025, 2026]
                   If None, crawls current year only
        """
        if years is None:
            years = [2026]
        self.years = years if isinstance(years, list) else [years]

    def fetch_all_papers(self):
        """Fetch papers from all specified years"""
        all_papers = []
        for year in self.years:
            print(f"\n--- Fetching S&P {year} ---")
            papers = self.fetch_papers_for_year(year)
            all_papers.extend(papers)
        
        print(f"\nTotal: {len(all_papers)} papers from {len(self.years)} years")
        return all_papers

    def fetch_papers_for_year(self, year):
        """Fetch papers for a specific year"""
        url = f"https://sp{year}.ieee-security.org/accepted-papers.html"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching S&P {year}: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        # Find all paper entries
        paper_entries = soup.find_all('div', class_='list-group-item')
        
        for entry in paper_entries:
            paper = self._parse_paper(entry, year, url)
            if paper:
                papers.append(paper)

        print(f"Found {len(papers)} papers for S&P {year}")
        return papers

    def _parse_paper(self, entry, year, url):
        """Parse a single paper entry with completeness detection"""
        try:
            # Extract title
            title_link = entry.find('a', {'data-toggle': 'collapse'})
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            title = title.replace('☰', '').strip()
            
            # Extract authors
            authors = []
            author_div = entry.find('div', class_='authorlist')
            if author_div:
                author_text = author_div.get_text(strip=True)
                authors = [a.strip() for a in author_text.split(',') if a.strip()]
            
            # Detect data completeness
            # For now, we only have title and authors
            # Abstract would be in a different section if available
            data_completeness = 'title_only' if not authors else 'with_authors'
            
            return {
                'title': title,
                'authors': authors,
                'conference': f'IEEE S&P {year}',
                'year': year,
                'source_url': url,
                'data_completeness': data_completeness,
                'abstract': None,  # To be filled later if available
                'pdf_url': None    # To be filled later if available
            }
        except Exception as e:
            print(f"Error parsing paper: {e}")
            return None

    def save_papers(self, papers, output_dir='data/raw/papers'):
        """Save papers to JSON file"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/sp_multi_{timestamp}.json"
        
        data = {
            'source': 'IEEE S&P',
            'years': self.years,
            'fetched_at': datetime.now().isoformat(),
            'total_papers': len(papers),
            'papers': papers
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved to {filename}")
        return filename


def main():
    # Crawl multiple years
    crawler = SPCrawler(years=[2024, 2025, 2026])
    papers = crawler.fetch_all_papers()
    crawler.save_papers(papers)


if __name__ == '__main__':
    main()
