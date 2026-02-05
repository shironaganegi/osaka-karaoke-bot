from bs4 import BeautifulSoup
from datetime import datetime
from shared.utils import setup_logging, safe_requests_get

logger = setup_logging(__name__)

def fetch_github_trending(language=None):
    """
    Fetches trending repositories from GitHub.
    """
    url = "https://github.com/trending"
    if language:
        url += f"/{language}"
    
    logger.info(f"Fetching GitHub Trending: {url}")
    
    response = safe_requests_get(url)
    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    repos = []

    for article in soup.select('article.Box-row'):
        try:
            title_tag = article.select_one('h2 a')
            relative_link = title_tag.get('href')
            full_name = relative_link.strip().lstrip('/')
            owner, repo_name = full_name.split('/')
            url = f"https://github.com{relative_link}"
            
            description_tag = article.select_one('p')
            description = description_tag.get_text(strip=True) if description_tag else "No description"

            stars_tag = article.select_one('a[href$="/stargazers"]')
            stars_text = stars_tag.get_text(strip=True).replace(',', '') if stars_tag else "0"
            stars = int(stars_text)

            daily_stars_tag = article.select_one('span.d-inline-block.float-sm-right')
            daily_stars = 0
            if daily_stars_tag:
                 text = daily_stars_tag.get_text(strip=True)
                 daily_stars = int(text.split()[0].replace(',', ''))

            repos.append({
                "source": "github",
                "name": repo_name,
                "owner": owner,
                "url": url,
                "description": description,
                "stars": stars,
                "daily_stars": daily_stars,
                "language": language if language else "all",
                "fetched_at": datetime.now().isoformat()
            })
        except Exception as e:
            logging.warning(f"Error parsing a repo: {e}")
            continue

    return repos
