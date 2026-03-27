import os
import re

template_dir = 'templates'
form_regex = re.compile(r'(<form[^>]+method=[\'"]POST[\'"][^>]*>)', re.IGNORECASE)
csrf_input = '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>'

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'name="csrf_token"' not in content:
                new_content = form_regex.sub(rf'\1{csrf_input}', content)
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Injected CSRF into {filepath}")
