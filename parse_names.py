import re

def extract_professors():
    # 1. Open the massive HTML file
    try:
        with open('raw_professors.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
    except FileNotFoundError:
        print("Error: Could not find 'raw_professors.html'. Make sure it is in the same folder.")
        return

    # 2. Use Regular Expressions to find everything inside title="..."
    # We specifically look for the FIText class to ensure we only grab the names
    pattern = r'<a class="FIText" title="(.*?)">'
    raw_matches = re.findall(pattern, html_content)

    # 3. Clean the data (Remove duplicates, "Null", and "(All)")
    clean_professors = []
    for name in raw_matches:
        # Decode HTML entities (like &amp; for &) just in case
        clean_name = name.replace("&amp;", "&").strip()
        
        if clean_name not in ["(All)", "Null"] and clean_name not in clean_professors:
            clean_professors.append(clean_name)

    # 4. Save to a clean text file
    with open('professor_list.txt', 'w', encoding='utf-8') as output_file:
        for prof in clean_professors:
            output_file.write(f"{prof}\n")

    # 5. Print the exact format needed for your API Scraper
    print(f"Successfully extracted {len(clean_professors)} unique professors!")
    print("\n--- COPY AND PASTE THIS INTO YOUR api_scraper.py ---")
    print("PROFESSOR_LIST = [")
    for prof in clean_professors[:5]: # Print the first 5 as an example
        print(f'    "{prof}",')
    print("    # ... check professor_list.txt for the rest!")
    print("]")

if __name__ == "__main__":
    extract_professors()