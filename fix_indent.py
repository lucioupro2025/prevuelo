with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the problematic section
old = """# Si el drone está en espera en base, posicionarlo en el nuevo home point
if sim_state['drone']['status'] == "idle":
sim_state['drone']['position']['x'] = sim_state['field']['home_point']['x']
sim_state['drone']['position']['y'] = sim_state['field']['home_point']['y']
sim_state['drone']['altitude'] = 0.0"""

new = """# Si el drone está en espera en base, posicionarlo en el nuevo home point
if sim_state['drone']['status'] == "idle":
    sim_state['drone']['position']['x'] = sim_state['field']['home_point']['x']
    sim_state['drone']['position']['y'] = sim_state['field']['home_point']['y']
    sim_state['drone']['altitude'] = 0.0"""

if old in content:
    content = content.replace(old, new)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Fixed indentation")
else:
    print("❌ Pattern not found")