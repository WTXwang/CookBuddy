"""Test profile extractor logic"""
import sys, json, tempfile, shutil
sys.path.insert(0, '.')

from profiles.store import ProfileStore
from profiles.extractor import apply_changes

tmp = tempfile.mkdtemp()
store = ProfileStore(tmp)

# Setup
p = store.update_preferences(1, flavor=['辣'], allergens=['花生'], equipment=['炒锅'])

# LLM changes
changes = [
    {'field': 'allergens', 'action': 'remove', 'value': '花生'},
    {'field': 'equipment', 'action': 'add', 'value': '烤箱'},
    {'field': 'flavor', 'action': 'add', 'value': '清淡'},
]
updated = apply_changes(p, changes)

# Verify
assert updated is True, 'apply_changes should return True'
assert '花生' not in p.allergens, f'allergens should not contain 花生: {p.allergens}'
assert '烤箱' in p.equipment, f'equipment should contain 烤箱: {p.equipment}'
assert '清淡' in p.preferences.flavor, f'flavor should contain 清淡: {p.preferences.flavor}'
assert '辣' in p.preferences.flavor, f'flavor should still contain 辣: {p.preferences.flavor}'
assert '炒锅' in p.equipment, f'equipment should still contain 炒锅: {p.equipment}'

# Save and verify persistence
store.save(p)
saved = json.loads(open(f'{store._dir}/1.json', encoding='utf-8').read())
assert '花生' not in saved['allergens'], f'saved allergens should not contain 花生'
assert '烤箱' in saved['equipment'], 'saved equipment should contain 烤箱'
assert '清淡' in saved['preferences']['flavor'], 'saved flavor should contain 清淡'

# Print JSON result for inspection
result = {'status': 'PASS', 'profile': json.loads(p.model_dump_json(ensure_ascii=False))}
print(json.dumps(result, ensure_ascii=False))

shutil.rmtree(tmp)
