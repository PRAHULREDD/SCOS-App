import os
import glob

app_dir = r'c:\Users\rr001\Downloads\SCOS\backend\static\app'
html_files = glob.glob(os.path.join(app_dir, '*', 'index.html'))

print(f"Found {len(html_files)} files to process.")

for html_file in html_files:
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'viewport-fit=cover' in content and 'capacitor.js' in content:
        continue

    content = content.replace(
        '<meta content="width=device-width, initial-scale=1.0" name="viewport"/>',
        '<meta content="width=device-width, initial-scale=1.0, viewport-fit=cover" name="viewport"/>'
    )
    
    injection = """
    <script src="https://cdn.jsdelivr.net/npm/@capacitor/core/dist/capacitor.js"></script>
    <script src="../../js/mobile.js"></script>
    <style>body { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }</style>
</head>"""
    content = content.replace('</head>', injection)

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(content)
        
print('Done!')
