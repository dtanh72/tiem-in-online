import os

template_dir = 'templates'
target = "const formData = new FormData();"
replacement = "const formData = new FormData(); formData.append('csrf_token', '{{ csrf_token() }}');"

count = 0
for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if target in content and "formData.append('csrf_token'" not in content:
                new_content = content.replace(target, replacement)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Fixed CSRF in {filepath}")
                count += 1

print(f"Total files fixed: {count}")
