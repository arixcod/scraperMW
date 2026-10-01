from pathlib import Path
import json
import py_compile

from context_rules import apply_context_awareness, apply_internet_updates, find_missing_contextual

root = Path(__file__).parent
py_compile.compile(str(root / 'app.py'), doraise=True)
py_compile.compile(str(root / 'context_rules.py'), doraise=True)
print('[ OK ] Python syntax')

schemas = {}
for fn in ['temple.schema.json', 'temple.enhanced.schema.json', 'temple.v3.schema.json']:
    schemas[fn] = json.load(open(root / fn, encoding='utf-8'))
    print('[ OK ]', fn, 'valid JSON')

text = (root / 'app.py').read_text(encoding='utf-8')
checks = [
    'Use MandirWiki schema v3 (recommended)',
    'research_missing_on_internet',
    'web_search',
    'apply_context_awareness',
    'apply_internet_updates',
    'Search Internet for Missing Data',
    'gufaTimings applies ONLY',
]
for c in checks:
    assert c in text, c

for removed in ['google_text_search', 'google_route', 'uber_price_estimates', 'ola_ride_estimates', 'GOOGLE_MAPS_API_KEY', 'UBER_API_TOKEN', 'OLA_APP_TOKEN']:
    assert removed not in text, removed
print('[ OK ] provider-specific credentials/integrations removed')

v3 = schemas['temple.v3.schema.json']
assert 'nearbyServices' not in v3['properties']
assert 'travelUtilities' not in v3['properties']
assert 'googleMapsUrl' not in v3['properties']['generalInfo']['properties']
assert 'googleMapsUrl' not in v3['$defs']['nearby']['properties']
print('[ OK ] recommended schema cleaned of Google/ride-only fields')

# Regression: Mahakal should not receive gufa timings just because a special darshan/aarti exists.
sample_path = root / 'mahakal-v3-sample.json'
if sample_path.exists():
    sample = json.load(open(sample_path, encoding='utf-8'))
else:
    sample = {
        'generalInfo': {'templeName': 'Mahakaleshwar Temple', 'templeDescription': 'Jyotirlinga temple in Ujjain', 'location': 'Ujjain', 'deity': 'Shiva', 'trekPoints': [], 'dressCode': None, 'fullAddress': None, 'coordinates': None},
        'templeTimings': {'mandirTimings': {}, 'gufaTimings': {'applicable': True, 'reason': None, 'morningOpen': '04:00 AM', 'morningClose': '06:00 AM', 'eveningOpen': None, 'eveningClose': None}, 'aartis': [], 'specialAccessTimings': []},
    }
cleaned = apply_context_awareness(sample, v3, evidence=[])
g = (cleaned.get('templeTimings') or {}).get('gufaTimings')
assert isinstance(g, dict) and g.get('applicable') is False, g
assert not any(p.startswith('templeTimings.gufaTimings') for p in find_missing_contextual(cleaned)), find_missing_contextual(cleaned)
print('[ OK ] context-aware gufa rule')
from jsonschema import Draft202012Validator
sample_errors = list(Draft202012Validator(v3).iter_errors(cleaned))
assert not sample_errors, [e.message for e in sample_errors[:5]]
print('[ OK ] Mahakal sample remains valid under cleaned v3 schema')

# Regression: wider-web merge can fill a missing path, but cannot overwrite a populated value.
base = {'x': None, 'y': 'keep'}
results = [
    {'path': 'x', 'valueJson': '"filled"'},
    {'path': 'y', 'valueJson': '"overwrite"'},
]
merged, applied, rejected = apply_internet_updates(base, results, ['x', 'y'])
assert merged == {'x': 'filled', 'y': 'keep'}
assert len(applied) == 1 and len(rejected) == 1
print('[ OK ] missing-only web merge protection')

print('All local preflight checks passed.')
