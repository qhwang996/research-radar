"""
NDSS Conference Paper Crawler - Multi-year support
"""
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path


class NDSSCrawler:
    def __init__(self, years=None):
        """
        Args:
            years: list of years to crawl, e.g. [2022, 2023, 2024, 2025, 2026]
        """
        if years is None:
            years = [2026]
        self.years = years if isinstance(years, list) else [years]

    def fetch_all_papers(self):
        """Fetch papers from all specified years"""
        all_papers = []
        for year in self.years:
            print(f"\n--- Fetching NDSS {year} ---")
            papers = self.fetch_papers_for_year(year)
            all_papers.extend(papers)
        
        print(f"\nTotal: {len(all_papers)} papers from {len(self.years)} years")
        return all_papers

    def fetch_papers_for_year(self, year):
        """Fetch papers for a specific year"""
        url = f"https://www.ndss-symposium.org/ndss{year}/accepted-papers/"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching NDSS {year}: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        papers = []

        # Find all paper entries
        paper_entries = soup.find_all('div', class_='pt-cv-content-item')
        
        for entry in paper_entries:
            paper = self._parse_paper(entry, year, url)
            if paper:
                papers.append(paper)

        print(f"Found {len(papers)} papers for NDSS {year}")
        return papers

    def _parse_paper(self, entry, year, url):
        """Parse a single paper entry"""
        try:
            title_elem = entry.find('h2', class_='pt-cv-title')
            if not title_elem:
                return None
            
            title_link = title_elem.find('a')
            title = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)
            paper_url = title_link.get('href', '') if title_link else ''
            
            authors = []
            author_div = entry.find('div', class_='pt-cv-ctf-value')
            if author_div:
                author_p = author_div.find('p')
                if author_p:
                    author_text = author_p.get_text(strip=True)
                    authors = [a.strip() for a in author_text.split(',')]
            
            data_completeness = 'title_only' if not authors else 'with_authors'
            
            return {
                'title': title,
                'authors': authors,
                'paper_url': paper_url,
                'conference': f'NDSS {year}',
                'year': year,
                'source_url': url,
                'data_completeness': data_completeness,
                'abstract': None,
                'pdf_url': None
            }
        except Exception as e:
            print(f"Error parsing paper: {e}")
            return None

    def save_papers(self, papers, output_dir='data/raw/papers'):
        """Save papers to JSON file"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/ndss_multi_{timestamp}.json"
        
        data = {
            'source': 'NDSS',
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
    # Crawl 5 years: 2022-2026
    crawler = NDSSCrawler(years=[2022, 2023, 2024, 2025, 2026])
    papers = crawler.fetch_all_papers()
    crawler.save_papers(papers)


if __name__ == '__main__':
    main()
