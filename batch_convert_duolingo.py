"""
Batch Duolingo Guidebook Converter
Asynchronously converts multiple Duolingo guidebook pages and combines them into one file
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from typing import List, Tuple, Optional

# Import the extraction functions from the original script
def extract_dialog_text(phrase_div):
    """Extract text from a dialog phrase, preserving spacing"""
    text_div = phrase_div.find('div', class_='')
    if not text_div:
        return None
    
    german_parts = []
    for span in text_div.find_all('span', class_='dotted'):
        german_parts.append(span.get_text())
    
    german_text = ' '.join(german_parts)
    
    for content in text_div.children:
        if isinstance(content, str):
            text = content.strip()
            if text in ['.', '?', '!', ',']:
                german_text += text
                break
    
    english_span = text_div.find('span', class_='cAF')
    english_text = english_span.get_text() if english_span else ''
    
    if german_text and english_text:
        return f"{german_text}\n{english_text}"
    elif german_text:
        return german_text
    
    return None

def process_dialog(dialog_div):
    """Extract complete dialog with proper formatting"""
    lines = []
    storylines = dialog_div.find_all('div', class_='storyline')
    
    for storyline in storylines:
        phrase = storyline.find('div', class_='phrase')
        if phrase:
            text = extract_dialog_text(phrase)
            if text:
                lines.append(text)
    
    if lines:
        return '\n\n'.join(lines)
    return None

def process_tip(tip_div):
    """Extract and format tip as blockquote, preserving order and spacing"""
    lines = []
    
    title = tip_div.find('h3')
    if title:
        lines.append(f"> **{title.get_text()}**")
        lines.append(">")
    
    for element in tip_div.children:
        if not hasattr(element, 'name'):
            continue
        
        if element.name == 'p':
            text = element.get_text()
            if text and text.strip():
                lines.append(f"> {text}")
                lines.append(">")
        
        elif element.name == 'div' and 'illustration' in element.get('class', []):
            # Collect image and caption data
            img_src = None
            caption_german = None
            caption_english = None
            
            for child in element.children:
                if not hasattr(child, 'name'):
                    continue
                
                if child.name == 'img':
                    src = child.get('src', '')
                    if src and 'yandex' not in src:
                        img_src = src
                
                elif child.name == 'div' and 'caption' in child.get('class', []):
                    text_divs = child.find_all('div', recursive=False)
                    
                    for inner_div in text_divs:
                        if 'playback' in inner_div.get('class', []):
                            continue
                        
                        german_parts = []
                        english_text = ''
                        
                        for content in inner_div.children:
                            if isinstance(content, str):
                                german_parts.append(content)
                            elif content.name == 'span':
                                if 'cAF' in content.get('class', []):
                                    english_text = content.get_text()
                                else:
                                    german_parts.append(content.get_text())
                            elif content.name == 'br':
                                break
                        
                        caption_german = ''.join(german_parts).strip()
                        caption_english = english_text.strip()
            
            # Build the HTML figure with image and caption
            if img_src:
                lines.append(f">")
                
                caption_parts = []
                if caption_german:
                    caption_parts.append(caption_german)
                if caption_english:
                    caption_parts.append(f"<br><em>{caption_english}</em>")
                
                caption_html = ''.join(caption_parts) if caption_parts else ''
                
                if caption_html:
                    lines.append(f"> <figure><img src=\"{img_src}\" alt=\"Illustration\"><figcaption>{caption_html}</figcaption></figure>")
                else:
                    lines.append(f"> <figure><img src=\"{img_src}\" alt=\"Illustration\"></figure>")
                
                lines.append(f">")
        
        elif element.name == 'hr':
            pass
    
    while lines and lines[-1] == ">":
        lines.pop()
    
    return '\n'.join(lines) if lines else None

def extract_content(html: str, base_url: str, lesson_number: int = None) -> str:
    """Extract and format content from the HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    markdown_content = []
    
    guide = soup.find('div', class_='guide')
    if not guide:
        return "Error: Could not find guide content"
    
    title_elem = guide.find('h3', class_='zero')
    if title_elem:
        title_text = title_elem.get_text(strip=True)
        title_text = re.sub(r'.*Guidebook:\s*', '', title_text)
        
        # Add lesson number prefix if provided
        if lesson_number is not None:
            title_text = f"Lesson {lesson_number}: {title_text}"
        
        markdown_content.append(f"# {title_text}\n")
    
    for element in guide.children:
        if not hasattr(element, 'name'):
            continue
        
        if element.name in ['h3', 'h5']:
            text = element.get_text(strip=True)
            if element.name == 'h3' and 'zero' not in element.get('class', []):
                markdown_content.append(f"\n### {text}\n")
            elif element.name == 'h5':
                markdown_content.append(f"\n##### {text}\n")
        
        elif element.name == 'hr':
            if 'blue' not in element.get('class', []):
                markdown_content.append("\n---\n")
        
        elif element.name == 'div' and 'dialogue' in element.get('class', []):
            dialog_text = process_dialog(element)
            if dialog_text:
                markdown_content.append(f"\n{dialog_text}\n")
        
        elif element.name == 'div' and 'guide-tip' in element.get('class', []):
            tip_text = process_tip(element)
            if tip_text:
                markdown_content.append(f"\n{tip_text}\n")
    
    return '\n'.join(markdown_content)

async def fetch_page_async(session: aiohttp.ClientSession, url: str, unit_num: int) -> Tuple[int, Optional[str]]:
    """Asynchronously fetch a single page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"Fetching Unit {unit_num}...")
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                html = await response.text()
                content = extract_content(html, url, unit_num)  # Pass unit_num as lesson_number
                print(f"✓ Unit {unit_num} completed")
                return (unit_num, content)
            else:
                print(f"✗ Unit {unit_num} failed (Status: {response.status})")
                return (unit_num, None)
    except Exception as e:
        print(f"✗ Unit {unit_num} error: {e}")
        return (unit_num, None)

async def fetch_all_pages(start: int = 1, end: int = 156) -> List[Tuple[int, Optional[str]]]:
    """Asynchronously fetch all pages"""
    base_url = "https://duome.eu/guidebook/en/de/{}"
    
    # Create connection limits to avoid overwhelming the server
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for i in range(start, end + 1):
            url = base_url.format(i)
            task = fetch_page_async(session, url, i)
            tasks.append(task)
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)
        return results

def combine_and_save(results: List[Tuple[int, Optional[str]]], filename: str = 'all_duolingo_guidebooks.md'):
    """Combine all results into a single markdown file, sorted by unit number"""
    # Filter out None results and sort by unit number
    valid_results = [(num, content) for num, content in results if content is not None]
    valid_results.sort(key=lambda x: x[0])
    
    print(f"\n{'='*60}")
    print(f"Successfully fetched {len(valid_results)} out of {len(results)} units")
    print(f"{'='*60}\n")
    
    # Combine all content with separators
    combined_content = []
    for i, (unit_num, content) in enumerate(valid_results):
        combined_content.append(content)
        # Add separator between units (but not after the last one)
        if i < len(valid_results) - 1:
            combined_content.append("\n\n---\n\n")
    
    # Write to file
    final_content = ''.join(combined_content)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    print(f"✓ All content saved to {filename}")
    print(f"  Total units: {len(valid_results)}")
    print(f"  File size: {len(final_content):,} characters")
    
    # Show failed units if any
    failed_units = [num for num, content in results if content is None]
    if failed_units:
        print(f"\n⚠ Failed units: {failed_units}")
    
    return filename

async def main_async(start: int = 1, end: int = 156, output_file: str = 'all_duolingo_guidebooks.md'):
    """Main async function"""
    print(f"Starting batch conversion for units {start} to {end}...")
    print(f"{'='*60}\n")
    
    # Fetch all pages
    results = await fetch_all_pages(start, end)
    
    # Combine and save
    print(f"\n{'='*60}")
    print("Combining results...")
    print(f"{'='*60}\n")
    
    filename = combine_and_save(results, output_file)
    
    return filename

def main(start: int = 1, end: int = 156, output_file: str = 'all_duolingo_guidebooks.md'):
    """Main function - entry point"""
    # Run the async main function
    filename = asyncio.run(main_async(start, end, output_file))
    
    print(f"\n{'='*60}")
    print("✓ BATCH CONVERSION COMPLETE!")
    print(f"{'='*60}")
    
    return filename

# For Google Colab usage
if __name__ == "__main__":
    # Install required packages (run this in a separate cell in Colab)
    # !pip install aiohttp beautifulsoup4
    
    # Run the batch conversion
    # You can customize the range and output filename
    output_filename = main(start=1, end=156, output_file='all_duolingo_guidebooks.md')
    
    # Download file to local machine (Colab)
    try:
        from google.colab import files
        files.download(output_filename)
    except:
        print("\nNot running in Google Colab - file saved locally")