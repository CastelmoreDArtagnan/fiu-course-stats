import json
import urllib.parse

def build_sitemap():
    print("Reading FIU database...")
    with open('fiu_data.json', 'r') as f:
        data = json.load(f)
        
    urls = []
    base_url = "https://www.statsforgood.com/"
    
    # 1. Homepage
    urls.append(base_url)
    
    # 2. Departments and Courses
    for dept, dept_data in data.get('departments', {}).items():
        urls.append(f"{base_url}?dept={dept}")
        for course_code in dept_data.get('courses', {}).keys():
            safe_course = course_code.replace(" ", "")
            urls.append(f"{base_url}?course={safe_course}")
            
    # 3. Professors
    for prof in data.get('professors', {}).keys():
        safe_prof = urllib.parse.quote_plus(prof)
        urls.append(f"{base_url}?prof={safe_prof}")
        
    # Generate the XML
    print("Writing sitemap.xml...")
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for url in urls:
        xml.append('  <url>')
        xml.append(f'    <loc>{url.replace("&", "&amp;")}</loc>')
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append('  </url>')
        
    xml.append('</urlset>')
    
    with open('sitemap.xml', 'w', encoding='utf-8') as f:
        f.write('\n'.join(xml))
        
    print(f"Success! Generated {len(urls)} programmatic SEO links. (Well under the 50,000 URL limit)")

if __name__ == "__main__":
    build_sitemap()