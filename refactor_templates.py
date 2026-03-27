import os
import ast
import re
import json

def get_route_mapping():
    mapping = {}
    d = 'routes'
    files = [f for f in os.listdir(d) if f.endswith('.py')]
    for f in files:
        with open(os.path.join(d, f), 'r', encoding='utf-8') as file:
            tree = ast.parse(file.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for d_node in node.decorator_list:
                        if isinstance(d_node, ast.Call) and getattr(d_node.func, 'attr', '') == 'route':
                            bp_name = getattr(d_node.func.value, 'id', '').replace('_bp', '')
                            mapping[node.name] = f"{bp_name}.{node.name}"
    return mapping

def update_templates(mapping):
    template_dir = 'templates'
    updated_files = 0
    total_files = 0
    
    for root, dirs, files in os.walk(template_dir):
        for filename in files:
            if filename.endswith('.html'):
                total_files += 1
                filepath = os.path.join(root, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                def repl(match):
                    quote = match.group(1)
                    func_name = match.group(2)
                    if func_name in mapping:
                        new_func_name = mapping[func_name]
                        return f"url_for({quote}{new_func_name}{quote}"
                    return match.group(0) # Unchanged
                    
                # Regex to match url_for('route_name' OR url_for("route_name"
                new_content = re.sub(r'url_for\(([\'"])([a-zA-Z0-9_]+)\1', repl, content)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    updated_files += 1
                    print(f"Updated {filepath}")
                    
    print(f"\\nTotal HTML files updated: {updated_files} / {total_files}")

if __name__ == "__main__":
    mapping = get_route_mapping()
    print("Mapping built with", len(mapping), "routes.")
    update_templates(mapping)
