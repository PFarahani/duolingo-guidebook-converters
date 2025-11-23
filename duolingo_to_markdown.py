"""
Duolingo Guidebook to Markdown/HTML Converter
Extracts content from Duolingo guidebook pages and converts to Notion-compatible format
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def fetch_page(url):
    """Fetch the HTML content of the page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def extract_dialog_text(phrase_div):
    """Extract text from a dialog phrase, preserving spacing"""
    # Find the div containing the actual text (not the playback div)
    text_div = phrase_div.find('div', class_='')
    if not text_div:
        return None
    
    # Extract German text (the spans with words)
    german_parts = []
    for span in text_div.find_all('span', class_='dotted'):
        german_parts.append(span.get_text())  # No strip!
    
    german_text = ' '.join(german_parts)
    
    # Add punctuation if it exists after spans
    for content in text_div.children:
        if isinstance(content, str):
            text = content.strip()
            if text in ['.', '?', '!', ',']:
                german_text += text
                break
    
    # Extract English translation
    english_span = text_div.find('span', class_='cAF')
    english_text = english_span.get_text() if english_span else ''  # No strip!
    
    if german_text and english_text:
        return f"{german_text}\n{english_text}"
    elif german_text:
        return german_text
    
    return None

def process_dialog(dialog_div):
    """Extract complete dialog with proper formatting"""
    lines = []
    
    # Find all storylines in the dialog
    storylines = dialog_div.find_all('div', class_='storyline')
    
    for storyline in storylines:
        # Find phrase within storyline
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
    
    # Get the tip title
    title = tip_div.find('h3')
    if title:
        lines.append(f"> **{title.get_text()}**")  # No strip
        lines.append(">")
    
    # Process all direct children in order to maintain sequence
    for element in tip_div.children:
        if not hasattr(element, 'name'):
            continue
        
        # Paragraphs
        if element.name == 'p':
            text = element.get_text()  # No strip - preserve spacing!
            if text and text.strip():  # Only check if not empty
                lines.append(f"> {text}")
                lines.append(">")
        
        # Illustrations (with images and captions)
        elif element.name == 'div' and 'illustration' in element.get('class', []):
            # Collect image and caption data
            img_src = None
            caption_german = None
            caption_english = None
            
            # Process all children of illustration in order
            for child in element.children:
                if not hasattr(child, 'name'):
                    continue
                
                # Image
                if child.name == 'img':
                    src = child.get('src', '')
                    if src and 'yandex' not in src:  # Skip tracking pixels
                        img_src = src
                
                # Caption (dialog example within tip)
                elif child.name == 'div' and 'caption' in child.get('class', []):
                    # Caption has 2 divs: playback div and text div
                    # We need to find all divs and skip the playback one
                    text_divs = child.find_all('div', recursive=False)
                    
                    for inner_div in text_divs:
                        # Skip playback divs
                        if 'playback' in inner_div.get('class', []):
                            continue
                        
                        # This is the text div
                        german_parts = []
                        english_text = ''
                        
                        for content in inner_div.children:
                            if isinstance(content, str):
                                german_parts.append(content)
                            elif content.name == 'span':
                                if 'cAF' in content.get('class', []):
                                    # This is English translation
                                    english_text = content.get_text()
                                else:
                                    # This is part of German text
                                    german_parts.append(content.get_text())
                            elif content.name == 'br':
                                # BR separates German from English
                                break
                        
                        # Combine German parts
                        caption_german = ''.join(german_parts).strip()
                        caption_english = english_text.strip()
            
            # Now build the HTML figure with image and caption
            if img_src:
                lines.append(f">")
                
                # Build figcaption content
                caption_parts = []
                if caption_german:
                    caption_parts.append(caption_german)
                if caption_english:
                    caption_parts.append(f"<br><em>{caption_english}</em>")
                
                caption_html = ''.join(caption_parts) if caption_parts else ''
                
                # Build complete figure
                if caption_html:
                    lines.append(f"> <figure><img src=\"{img_src}\" alt=\"Illustration\"><figcaption>{caption_html}</figcaption></figure>")
                else:
                    lines.append(f"> <figure><img src=\"{img_src}\" alt=\"Illustration\"></figure>")
                
                lines.append(f">")
        
        # Horizontal rules within tips
        elif element.name == 'hr':
            pass  # Skip HR within tips, we handle separation with empty blockquotes
    
    # Remove trailing empty blockquote lines
    while lines and lines[-1] == ">":
        lines.pop()
    
    return '\n'.join(lines) if lines else None

def extract_content(html, base_url, lesson_number=None):
    """Extract and format content from the HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    
    markdown_content = []
    
    # Find the main guide div
    guide = soup.find('div', class_='guide')
    if not guide:
        return "Error: Could not find guide content"
    
    # Extract title
    title_elem = guide.find('h3', class_='zero')
    if title_elem:
        # Get just the text, not the links
        title_text = title_elem.get_text(strip=True)
        # Remove "German Guidebook" prefix if present
        title_text = re.sub(r'.*Guidebook:\s*', '', title_text)
        
        # Add lesson number prefix if provided
        if lesson_number is not None:
            title_text = f"Lesson {lesson_number}: {title_text}"
        
        markdown_content.append(f"# {title_text}\n")
    
    # Process all top-level children of guide in order
    for element in guide.children:
        if not hasattr(element, 'name'):
            continue
        
        # Headers
        if element.name in ['h3', 'h5']:
            text = element.get_text(strip=True)
            if element.name == 'h3' and 'zero' not in element.get('class', []):
                markdown_content.append(f"\n### {text}\n")
            elif element.name == 'h5':
                markdown_content.append(f"\n##### {text}\n")
        
        # Horizontal rules
        elif element.name == 'hr':
            if 'blue' not in element.get('class', []):
                markdown_content.append("\n---\n")
        
        # Dialogs
        elif element.name == 'div' and 'dialogue' in element.get('class', []):
            dialog_text = process_dialog(element)
            if dialog_text:
                markdown_content.append(f"\n{dialog_text}\n")
        
        # Tips
        elif element.name == 'div' and 'guide-tip' in element.get('class', []):
            tip_text = process_tip(element)
            if tip_text:
                markdown_content.append(f"\n{tip_text}\n")
    
    return '\n'.join(markdown_content)

def save_markdown(content, filename='duolingo_guidebook.md'):
    """Save content to a markdown file"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Content saved to {filename}")

def main(url, lesson_number=None):
    """Main function to convert Duolingo guidebook to Markdown"""
    print(f"Fetching content from: {url}")
    
    # Extract lesson number from URL if not provided
    if lesson_number is None:
        match = re.search(r'/(\d+)$', url)
        if match:
            lesson_number = int(match.group(1))
    
    try:
        html = fetch_page(url)
        print("Page fetched successfully!")
        
        print("Extracting and converting content...")
        markdown_content = extract_content(html, url, lesson_number)
        
        print("Conversion complete!")
        
        # Save to file
        save_markdown(markdown_content)
        
        # Also return the content for display
        return markdown_content
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# For Google Colab usage
if __name__ == "__main__":
    # Install required packages (run this in a separate cell in Colab)
    # !pip install requests beautifulsoup4
    
    # Example usage
    url = "https://duome.eu/guidebook/en/de/14"
    markdown_output = main(url)
    
    if markdown_output:
        print("\n" + "="*60)
        print("PREVIEW OF MARKDOWN OUTPUT:")
        print("="*60 + "\n")
        print(markdown_output)
        
        # Download file to local machine (Colab)
        try:
            from google.colab import files
            files.download('duolingo_guidebook.md')
        except:
            print("\nNot running in Google Colab - file saved locally")